-- Schema for the Personalised Book Recommendation System
-- A Book Club and Library in Eldoret, Kenya

DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS borrow_history;
DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS reservations;
DROP TABLE IF EXISTS preference_tags;

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',   -- 'member' or 'admin'
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    genre TEXT NOT NULL,
    subject TEXT,
    isbn TEXT,
    description TEXT,
    total_copies INTEGER NOT NULL DEFAULT 1,
    available_copies INTEGER NOT NULL DEFAULT 1,
    cover_color TEXT DEFAULT '#4a6fa5',
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE borrow_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date TEXT NOT NULL,
    due_date TEXT,
    return_date TEXT,
    status TEXT NOT NULL DEFAULT 'borrowed',  -- 'borrowed' or 'returned'
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    reservation_date TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'fulfilled', 'cancelled'
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

-- Cached/derived preference tags per member (genre -> weight), refreshed by the engine
CREATE TABLE preference_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    genre TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (member_id) REFERENCES members(id),
    UNIQUE(member_id, genre)
);
