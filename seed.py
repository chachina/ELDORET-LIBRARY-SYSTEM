"""
seed.py
=======
Pre-populates the database with realistic demo data so the recommendation
engine has something to learn from immediately:
  - 1 admin + 6 members
  - 24 books across 6 genres
  - borrowing history spread over the last 8 months (some returned, some active)
  - star ratings & reviews
  - a few pending reservations

Run automatically on first launch of app.py, or manually:
    python seed.py
"""

import sqlite3
import os
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "library.db")


BOOKS = [
    # title, author, genre, subject, isbn, description, copies, color
    ("Things Fall Apart", "Chinua Achebe", "African Literature", "Classic Fiction", "9780385474542",
     "A powerful story of pre-colonial life in Nigeria and the arrival of European colonialism.", 3, "#7a5c3e"),
    ("Half of a Yellow Sun", "Chimamanda Ngozi Adichie", "African Literature", "Historical Fiction", "9780007200283",
     "A novel set during the Nigerian Civil War, following three intertwined lives.", 2, "#a9542f"),
    ("The River Between", "Ngugi wa Thiong'o", "African Literature", "Classic Fiction", "9780435905484",
     "Two rival villages in Kenya divided by tradition and the coming of Christianity.", 2, "#8c6d46"),
    ("Petals of Blood", "Ngugi wa Thiong'o", "African Literature", "Political Fiction", "9780435908455",
     "A searing critique of post-independence Kenya told through four intertwined lives.", 2, "#6f4e37"),
    ("Americanah", "Chimamanda Ngozi Adichie", "African Literature", "Contemporary Fiction", "9780307455925",
     "A sweeping story of love, race, and identity between Nigeria, the US and the UK.", 3, "#b5651d"),

    ("A Brief History of Time", "Stephen Hawking", "Science", "Physics", "9780553380163",
     "An accessible exploration of cosmology, black holes, and the nature of time.", 2, "#2e6f95"),
    ("Sapiens", "Yuval Noah Harari", "Science", "Anthropology", "9780062316097",
     "A sweeping history of how Homo sapiens came to dominate the planet.", 3, "#1f5673"),
    ("The Selfish Gene", "Richard Dawkins", "Science", "Biology", "9780198788607",
     "A landmark work explaining evolution from the gene's point of view.", 2, "#27688a"),
    ("Cosmos", "Carl Sagan", "Science", "Astronomy", "9780345539434",
     "A classic tour of the universe and humanity's place within it.", 2, "#1c4e66"),
    ("The Gene: An Intimate History", "Siddhartha Mukherjee", "Science", "Genetics", "9781476733500",
     "A history of genetics and its implications for medicine and society.", 2, "#225a78"),

    ("Guns, Germs, and Steel", "Jared Diamond", "History", "World History", "9780393354324",
     "An examination of why some civilisations developed faster than others.", 2, "#7e2f2f"),
    ("The Diary of a Young Girl", "Anne Frank", "History", "World War II", "9780553296983",
     "The wartime diary of a Jewish girl in hiding during the Nazi occupation.", 3, "#923a3a"),
    ("A People's History of the United States", "Howard Zinn", "History", "American History", "9780062397348",
     "American history told from the perspective of ordinary people.", 2, "#6b2424"),
    ("Kenya: A History Since Independence", "Charles Hornsby", "History", "Kenyan History", "9781848853594",
     "A detailed political history of Kenya from independence to the present.", 2, "#812e2e"),
    ("The Silk Roads", "Peter Frankopan", "History", "World History", "9781101912379",
     "A new history of the world told through the trade routes of Central Asia.", 2, "#7a2b2b"),

    ("Rich Dad Poor Dad", "Robert Kiyosaki", "Business", "Personal Finance", "9781612680194",
     "Lessons on money, investing, and financial independence.", 3, "#34693d"),
    ("The Lean Startup", "Eric Ries", "Business", "Entrepreneurship", "9780307887894",
     "A methodology for developing businesses and products through validated learning.", 2, "#2c5934"),
    ("Atomic Habits", "James Clear", "Business", "Self-Improvement", "9780735211292",
     "A practical guide to building good habits and breaking bad ones.", 3, "#3a7544"),
    ("Zero to One", "Peter Thiel", "Business", "Entrepreneurship", "9780804139298",
     "Notes on startups and how to build the future.", 2, "#2e5e38"),
    ("Good to Great", "Jim Collins", "Business", "Management", "9780066620992",
     "Why some companies make the leap from good to great and others don't.", 2, "#386b41"),

    ("Dune", "Frank Herbert", "Science Fiction", "Space Opera", "9780441172719",
     "A epic saga of politics, religion, and ecology on the desert planet Arrakis.", 2, "#4a3b6b"),
    ("Neuromancer", "William Gibson", "Science Fiction", "Cyberpunk", "9780441569595",
     "The novel that defined the cyberpunk genre.", 2, "#3f3260"),
    ("The Three-Body Problem", "Liu Cixin", "Science Fiction", "Hard Sci-Fi", "9780765382030",
     "A first contact story spanning China's Cultural Revolution to the present day.", 2, "#473a6e"),
    ("Foundation", "Isaac Asimov", "Science Fiction", "Space Opera", "9780553293357",
     "The story of a mathematician who predicts the fall of a galactic empire.", 2, "#433662"),
]


MEMBERS = [
    ("Faith Chebet", "faith@example.com", "African Literature"),
    ("Brian Otieno", "brian@example.com", "Science Fiction"),
    ("Mercy Wanjiru", "mercy@example.com", "Business"),
    ("Kevin Kiprotich", "kevin@example.com", "History"),
    ("Grace Naliaka", "grace@example.com", "Science"),
    ("Dennis Mwangi", "dennis@example.com", "African Literature"),
]


def run(db_path=None):
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # --- Admin ---
    cur.execute(
        "INSERT INTO members (full_name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
        ("Library Administrator", "admin@library.co.ke", generate_password_hash("admin123")),
    )

    # --- Members ---
    member_ids = {}
    for full_name, email, fav_genre in MEMBERS:
        cur.execute(
            "INSERT INTO members (full_name, email, password_hash, role) VALUES (?, ?, ?, 'member')",
            (full_name, email, generate_password_hash("member123")),
        )
        member_ids[full_name] = (cur.lastrowid, fav_genre)

    # --- Books ---
    book_ids = []
    for title, author, genre, subject, isbn, desc, copies, color in BOOKS:
        cur.execute(
            """INSERT INTO books (title, author, genre, subject, isbn, description,
               total_copies, available_copies, cover_color)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (title, author, genre, subject, isbn, desc, copies, copies, color),
        )
        book_ids.append((cur.lastrowid, genre))

    # --- Borrow history + ratings: each member borrows mostly from their
    # favourite genre (to give the recommender clear signal) plus a couple
    # of random other genres, spread across the last 8 months. ---
    import random
    random.seed(42)
    today = date.today()

    for full_name, (member_id, fav_genre) in member_ids.items():
        fav_books = [b for b in book_ids if b[1] == fav_genre]
        other_books = [b for b in book_ids if b[1] != fav_genre]

        picks = random.sample(fav_books, k=min(3, len(fav_books)))
        picks += random.sample(other_books, k=2)

        for i, (book_id, genre) in enumerate(picks):
            days_ago = random.randint(10, 230)
            borrow_date = today - timedelta(days=days_ago)
            # Most are returned; the most recent one or two stay active
            if i >= len(picks) - 1 and days_ago < 20:
                status = "borrowed"
                return_date = None
                cur.execute(
                    "UPDATE books SET available_copies = available_copies - 1 WHERE id=?",
                    (book_id,),
                )
            else:
                status = "returned"
                return_date = (borrow_date + timedelta(days=random.randint(7, 14))).isoformat()

            due_date = (borrow_date + timedelta(days=14)).isoformat()
            cur.execute(
                """INSERT INTO borrow_history (member_id, book_id, borrow_date, due_date, return_date, status)
                   VALUES (?,?,?,?,?,?)""",
                (member_id, book_id, borrow_date.isoformat(), due_date, return_date, status),
            )

            # Rate most returned books
            if status == "returned" and random.random() < 0.8:
                rating = random.choice([3, 4, 4, 5, 5]) if genre == fav_genre else random.randint(2, 5)
                reviews = {
                    5: "Absolutely loved this one — couldn't put it down.",
                    4: "Really enjoyed it, well worth the read.",
                    3: "Decent read, met my expectations.",
                    2: "Not really my taste, but well written.",
                }
                cur.execute(
                    "INSERT INTO ratings (member_id, book_id, rating, review, created_at) VALUES (?,?,?,?,?)",
                    (member_id, book_id, rating, reviews.get(rating, "Good book."),
                     (borrow_date + timedelta(days=15)).isoformat()),
                )

    # --- A few pending reservations ---
    sample_members = list(member_ids.values())[:3]
    sample_books = random.sample(book_ids, k=3)
    for (member_id, _), (book_id, _) in zip(sample_members, sample_books):
        cur.execute(
            "INSERT INTO reservations (member_id, book_id, status) VALUES (?, ?, 'pending')",
            (member_id, book_id),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    schema_path = os.path.join(BASE_DIR, "schema.sql")
    conn = sqlite3.connect(DB_PATH)
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    run()
    print("Seeded library.db with demo data.")
