"""
app.py
======
A Web-Based Personalised Book Recommendation System for Library Management
Book Club and Library, Eldoret, Kenya

Run with:  python app.py
Then open: http://127.0.0.1:5000

Demo logins (see seed.py):
  Admin   -> email: admin@library.co.ke      password: admin123
  Member  -> email: faith@example.com        password: member123
  Member  -> email: brian@example.com        password: member123
"""

import os
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

import recommender

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "library.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

app = Flask(__name__)
app.secret_key = "eldoret-library-recsys-secret-key-2026"


# ----------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db_if_needed():
    fresh = not os.path.exists(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    if fresh:
        with open(SCHEMA_PATH, "r") as f:
            db.executescript(f.read())
        db.commit()
    db.close()
    return fresh


# ----------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {
        "current_user_name": session.get("full_name"),
        "current_user_role": session.get("role"),
    }


# ----------------------------------------------------------------------
# Public / Auth routes
# ----------------------------------------------------------------------
@app.route("/")
def index():
    if session.get("user_id"):
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("home"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        db = get_db()
        existing = db.execute("SELECT id FROM members WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        db.execute(
            "INSERT INTO members (full_name, email, password_hash, role) VALUES (?, ?, ?, 'member')",
            (full_name, email, generate_password_hash(password)),
        )
        db.commit()
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM members WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['full_name'].split()[0]}!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("home"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ----------------------------------------------------------------------
# Member routes
# ----------------------------------------------------------------------
@app.route("/home")
@login_required
def home():
    db = get_db()
    member_id = session["user_id"]

    recs = recommender.get_recommendations(db, member_id)

    genre_filter = request.args.get("genre", "").strip()
    query = request.args.get("q", "").strip()

    sql = "SELECT * FROM books WHERE 1=1"
    params = []
    if genre_filter:
        sql += " AND genre = ?"
        params.append(genre_filter)
    if query:
        sql += " AND (title LIKE ? OR author LIKE ?)"
        params.extend([f"%{query}%", f"%{query}%"])
    sql += " ORDER BY title ASC"
    catalogue = db.execute(sql, params).fetchall()

    genres = [r["genre"] for r in db.execute("SELECT DISTINCT genre FROM books ORDER BY genre").fetchall()]

    return render_template(
        "home.html",
        recommendations=recs,
        catalogue=catalogue,
        genres=genres,
        selected_genre=genre_filter,
        query=query,
    )


@app.route("/book/<int:book_id>", methods=["GET", "POST"])
@login_required
def book_detail(book_id):
    db = get_db()
    member_id = session["user_id"]
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        abort(404)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "borrow":
            already = db.execute(
                "SELECT id FROM borrow_history WHERE member_id=? AND book_id=? AND status='borrowed'",
                (member_id, book_id),
            ).fetchone()
            if already:
                flash("You already have this book borrowed.", "warning")
            elif book["available_copies"] < 1:
                flash("No copies currently available. Try reserving instead.", "warning")
            else:
                today = date.today()
                due = today + timedelta(days=14)
                db.execute(
                    "INSERT INTO borrow_history (member_id, book_id, borrow_date, due_date, status) "
                    "VALUES (?, ?, ?, ?, 'borrowed')",
                    (member_id, book_id, today.isoformat(), due.isoformat()),
                )
                db.execute(
                    "UPDATE books SET available_copies = available_copies - 1 WHERE id = ?",
                    (book_id,),
                )
                db.commit()
                flash(f'"{book["title"]}" borrowed. Due back {due.isoformat()}.', "success")

        elif action == "reserve":
            db.execute(
                "INSERT INTO reservations (member_id, book_id, status) VALUES (?, ?, 'pending')",
                (member_id, book_id),
            )
            db.commit()
            flash(f'Reservation placed for "{book["title"]}".', "success")

        elif action == "rate":
            try:
                rating = int(request.form.get("rating", ""))
            except (TypeError, ValueError):
                rating = None
            review = request.form.get("review", "").strip()
            if rating is None or not (1 <= rating <= 5):
                flash("Please select a rating between 1 and 5 stars.", "danger")
                return redirect(url_for("book_detail", book_id=book_id))

            existing = db.execute(
                "SELECT id FROM ratings WHERE member_id=? AND book_id=?", (member_id, book_id)
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE ratings SET rating=?, review=?, created_at=? WHERE id=?",
                    (rating, review, datetime.now().isoformat(timespec="seconds"), existing["id"]),
                )
            else:
                db.execute(
                    "INSERT INTO ratings (member_id, book_id, rating, review) VALUES (?, ?, ?, ?)",
                    (member_id, book_id, rating, review),
                )
            db.commit()
            flash("Thanks for your rating!", "success")

        return redirect(url_for("book_detail", book_id=book_id))

    my_borrow = db.execute(
        "SELECT * FROM borrow_history WHERE member_id=? AND book_id=? AND status='borrowed'",
        (member_id, book_id),
    ).fetchone()
    my_rating = db.execute(
        "SELECT * FROM ratings WHERE member_id=? AND book_id=?", (member_id, book_id)
    ).fetchone()
    reviews = db.execute(
        """SELECT r.*, m.full_name FROM ratings r
           JOIN members m ON m.id = r.member_id
           WHERE r.book_id = ? ORDER BY r.created_at DESC""",
        (book_id,),
    ).fetchall()
    avg_rating_row = db.execute(
        "SELECT AVG(rating) AS avg_r, COUNT(*) AS n FROM ratings WHERE book_id=?", (book_id,)
    ).fetchone()

    return render_template(
        "book_detail.html",
        book=book,
        my_borrow=my_borrow,
        my_rating=my_rating,
        reviews=reviews,
        avg_rating=avg_rating_row["avg_r"],
        rating_count=avg_rating_row["n"],
    )


@app.route("/return/<int:borrow_id>", methods=["POST"])
@login_required
def return_book(borrow_id):
    db = get_db()
    member_id = session["user_id"]
    borrow = db.execute(
        "SELECT * FROM borrow_history WHERE id=? AND member_id=?", (borrow_id, member_id)
    ).fetchone()
    if not borrow:
        abort(404)
    if borrow["status"] == "returned":
        flash("This book was already returned.", "info")
        return redirect(url_for("my_account"))

    db.execute(
        "UPDATE borrow_history SET status='returned', return_date=? WHERE id=?",
        (date.today().isoformat(), borrow_id),
    )
    db.execute(
        "UPDATE books SET available_copies = available_copies + 1 WHERE id=?",
        (borrow["book_id"],),
    )
    db.commit()
    flash("Book marked as returned. Don't forget to rate it!", "success")
    return redirect(url_for("book_detail", book_id=borrow["book_id"]))


@app.route("/my-account")
@login_required
def my_account():
    db = get_db()
    member_id = session["user_id"]

    borrowed = db.execute(
        """SELECT bh.*, b.title, b.author, b.genre FROM borrow_history bh
           JOIN books b ON b.id = bh.book_id
           WHERE bh.member_id=? ORDER BY bh.borrow_date DESC""",
        (member_id,),
    ).fetchall()

    reservations = db.execute(
        """SELECT r.*, b.title, b.author FROM reservations r
           JOIN books b ON b.id = r.book_id
           WHERE r.member_id=? ORDER BY r.reservation_date DESC""",
        (member_id,),
    ).fetchall()

    my_ratings = db.execute(
        """SELECT r.*, b.title FROM ratings r
           JOIN books b ON b.id = r.book_id
           WHERE r.member_id=? ORDER BY r.created_at DESC""",
        (member_id,),
    ).fetchall()

    tags = db.execute(
        "SELECT genre, weight FROM preference_tags WHERE member_id=? ORDER BY weight DESC",
        (member_id,),
    ).fetchall()

    return render_template(
        "my_account.html",
        borrowed=borrowed,
        reservations=reservations,
        my_ratings=my_ratings,
        tags=tags,
    )


# ----------------------------------------------------------------------
# Admin routes
# ----------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    total_books = db.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
    total_members = db.execute("SELECT COUNT(*) c FROM members WHERE role='member'").fetchone()["c"]
    active_borrows = db.execute("SELECT COUNT(*) c FROM borrow_history WHERE status='borrowed'").fetchone()["c"]
    pending_reservations = db.execute("SELECT COUNT(*) c FROM reservations WHERE status='pending'").fetchone()["c"]

    most_borrowed = db.execute(
        """SELECT b.title, b.author, COUNT(*) AS borrow_count
           FROM borrow_history bh JOIN books b ON b.id = bh.book_id
           GROUP BY bh.book_id ORDER BY borrow_count DESC LIMIT 5"""
    ).fetchall()

    genre_stats = db.execute(
        """SELECT b.genre, COUNT(*) AS borrow_count
           FROM borrow_history bh JOIN books b ON b.id = bh.book_id
           GROUP BY b.genre ORDER BY borrow_count DESC"""
    ).fetchall()

    active_members = db.execute(
        """SELECT m.full_name, COUNT(*) AS activity
           FROM borrow_history bh JOIN members m ON m.id = bh.member_id
           GROUP BY bh.member_id ORDER BY activity DESC LIMIT 5"""
    ).fetchall()

    return render_template(
        "admin_dashboard.html",
        total_books=total_books,
        total_members=total_members,
        active_borrows=active_borrows,
        pending_reservations=pending_reservations,
        most_borrowed=most_borrowed,
        genre_stats=genre_stats,
        active_members=active_members,
    )


@app.route("/admin/books", methods=["GET", "POST"])
@admin_required
def admin_books():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            try:
                copies = max(1, int(request.form.get("total_copies", 1)))
            except (TypeError, ValueError):
                copies = 1
            db.execute(
                """INSERT INTO books (title, author, genre, subject, isbn, description,
                   total_copies, available_copies, cover_color)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    request.form["title"], request.form["author"], request.form["genre"],
                    request.form.get("subject", ""), request.form.get("isbn", ""),
                    request.form.get("description", ""),
                    copies, copies,
                    request.form.get("cover_color", "#4a6fa5"),
                ),
            )
            db.commit()
            flash("Book added.", "success")
        elif action == "delete":
            book_id = request.form.get("book_id")
            try:
                db.execute("DELETE FROM books WHERE id=?", (book_id,))
                db.commit()
                flash("Book removed.", "info")
            except sqlite3.IntegrityError:
                db.rollback()
                flash(
                    "This book can't be deleted because it has borrowing, rating, "
                    "or reservation history attached to it. Consider setting its "
                    "copies to 0 instead, or edit its details.",
                    "danger",
                )
        return redirect(url_for("admin_books"))

    books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
    return render_template("admin_books.html", books=books)


@app.route("/admin/books/<int:book_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if not book:
        abort(404)
    if request.method == "POST":
        try:
            new_total = max(1, int(request.form.get("total_copies", 1)))
        except (TypeError, ValueError):
            new_total = book["total_copies"]
        active_borrows = db.execute(
            "SELECT COUNT(*) c FROM borrow_history WHERE book_id=? AND status='borrowed'",
            (book_id,),
        ).fetchone()["c"]
        new_available = max(0, new_total - active_borrows)

        if new_total < active_borrows:
            flash(
                f"Total copies set to {new_total}, but {active_borrows} are currently "
                f"checked out. Available copies has been set to 0 until some are returned.",
                "warning",
            )

        db.execute(
            """UPDATE books SET title=?, author=?, genre=?, subject=?, isbn=?, description=?,
               total_copies=?, available_copies=?, cover_color=? WHERE id=?""",
            (
                request.form["title"], request.form["author"], request.form["genre"],
                request.form.get("subject", ""), request.form.get("isbn", ""),
                request.form.get("description", ""),
                new_total, new_available,
                request.form.get("cover_color", "#4a6fa5"),
                book_id,
            ),
        )
        db.commit()
        flash("Book updated.", "success")
        return redirect(url_for("admin_books"))
    return render_template("admin_edit_book.html", book=book)


@app.route("/admin/members")
@admin_required
def admin_members():
    db = get_db()
    members = db.execute(
        """SELECT m.*,
              (SELECT COUNT(*) FROM borrow_history bh WHERE bh.member_id = m.id) AS total_borrows
           FROM members m WHERE m.role='member' ORDER BY m.full_name"""
    ).fetchall()
    return render_template("admin_members.html", members=members)


@app.route("/admin/reservations", methods=["GET", "POST"])
@admin_required
def admin_reservations():
    db = get_db()
    if request.method == "POST":
        res_id = request.form.get("reservation_id")
        new_status = request.form.get("status")
        db.execute("UPDATE reservations SET status=? WHERE id=?", (new_status, res_id))
        db.commit()
        flash("Reservation updated.", "success")
        return redirect(url_for("admin_reservations"))

    reservations = db.execute(
        """SELECT r.*, b.title, b.author, m.full_name, m.email
           FROM reservations r
           JOIN books b ON b.id = r.book_id
           JOIN members m ON m.id = r.member_id
           ORDER BY r.reservation_date DESC"""
    ).fetchall()
    return render_template("admin_reservations.html", reservations=reservations)


@app.route("/admin/reports")
@admin_required
def admin_reports():
    db = get_db()

    most_borrowed = db.execute(
        """SELECT b.title, b.author, b.genre, COUNT(*) AS borrow_count
           FROM borrow_history bh JOIN books b ON b.id = bh.book_id
           GROUP BY bh.book_id ORDER BY borrow_count DESC LIMIT 10"""
    ).fetchall()

    active_members = db.execute(
        """SELECT m.full_name, m.email, COUNT(*) AS activity,
                  MAX(bh.borrow_date) AS last_activity
           FROM borrow_history bh JOIN members m ON m.id = bh.member_id
           GROUP BY bh.member_id ORDER BY activity DESC LIMIT 10"""
    ).fetchall()

    # Recommendation accuracy proxy (FR10): of all books members ended up
    # borrowing, what share were in their top genre tag at the time?
    accuracy_rows = db.execute(
        """SELECT bh.member_id, b.genre, bh.borrow_date
           FROM borrow_history bh JOIN books b ON b.id = bh.book_id"""
    ).fetchall()

    hits, total = 0, 0
    member_top_genre_cache = {}
    for row in accuracy_rows:
        mid = row["member_id"]
        if mid not in member_top_genre_cache:
            tag = db.execute(
                "SELECT genre FROM preference_tags WHERE member_id=? ORDER BY weight DESC LIMIT 1",
                (mid,),
            ).fetchone()
            member_top_genre_cache[mid] = tag["genre"] if tag else None
        total += 1
        if member_top_genre_cache[mid] == row["genre"]:
            hits += 1
    accuracy_pct = round((hits / total) * 100, 1) if total else 0.0

    genre_popularity = db.execute(
        """SELECT b.genre, COUNT(*) AS borrow_count
           FROM borrow_history bh JOIN books b ON b.id = bh.book_id
           GROUP BY b.genre ORDER BY borrow_count DESC"""
    ).fetchall()

    return render_template(
        "admin_reports.html",
        most_borrowed=most_borrowed,
        active_members=active_members,
        accuracy_pct=accuracy_pct,
        genre_popularity=genre_popularity,
    )


# ----------------------------------------------------------------------
# Error handlers
# ----------------------------------------------------------------------
@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You don't have permission to view this page."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


# ----------------------------------------------------------------------
if __name__ == "__main__":
    fresh = init_db_if_needed()
    if fresh:
        import seed
        seed.run(DB_PATH)
        print("Database created and seeded with demo data.")
    app.run(debug=True, host="127.0.0.1", port=5000)
