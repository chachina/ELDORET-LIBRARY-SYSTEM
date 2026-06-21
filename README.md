# Eldoret Book Club & Library — Personalised Book Recommendation System

A web-based library management system with a personalised "For You" book
recommendation engine, built with **Flask + SQLite**.

Implements the system proposed for Nimrod Masika Chachina (DIT-01-0357/2025,
Zetech University): User-Preference Tagging + a Weight-and-Rank scoring
algorithm that replaces static alphabetical browsing with personalised
recommendations.

## Features

**Members**
- Register / log in
- Browse & search the book catalogue (filter by genre)
- Personalised **"For You"** homepage section (top 8 picks, with a reason
  for each recommendation)
- Borrow & return books, place reservations
- Rate books (1–5 stars) and leave reviews
- "My Account" page showing borrowing history, reservations, ratings, and
  their auto-generated **preference tags**

**Admins**
- Dashboard with key stats (total books, members, active borrows, pending
  reservations, most-borrowed titles, most active members, genre breakdown)
- Add / edit / delete books
- View all members and their borrowing activity
- Manage reservations (fulfill / cancel)
- Reports: most-borrowed books, most active members, genre popularity, and
  a recommendation-accuracy metric (FR10)

## The Recommendation Engine (`recommender.py`)

1. **User-Preference Tagging** — rebuilds each member's genre weights from
   their borrow history and ratings, with a recency-decay half-life of 180
   days (recent activity counts more than old activity).
2. **Weight-and-Rank scoring** — ranks candidate books using:
   - Genre match (45%)
   - Peer rating (25%)
   - Popularity / recent borrow frequency (15%)
   - Recency/discovery bonus for newly added titles (15%)

## Running the App

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**

On first run, the database (`library.db`) is created automatically and
seeded with demo data (24 books across 6 genres, 6 members with realistic
borrowing/rating history, an admin account, and a few pending reservations).

### Demo Logins

| Role   | Email                  | Password   |
|--------|------------------------|------------|
| Admin  | admin@library.co.ke    | admin123   |
| Member | faith@example.com      | member123  |
| Member | brian@example.com      | member123  |
| Member | mercy@example.com      | member123  |
| Member | kevin@example.com      | member123  |
| Member | grace@example.com      | member123  |
| Member | dennis@example.com     | member123  |

To reset the demo data at any point, stop the server, delete `library.db`,
and restart `python app.py`.

## Project Structure

```
app.py              Flask routes (member + admin)
recommender.py       User-Preference Tagging + Weight-and-Rank engine
schema.sql            SQLite schema
seed.py               Demo data generator
templates/            Jinja2 templates
static/css/style.css  Styling
```
