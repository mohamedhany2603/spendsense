"""Seed script — demo data so a stranger sees the app working in minutes.

Creates demo@example.com / demo1234 and 3 calendar months of transactions
spanning known and unknown merchants. Known merchants hit the cached/rule
classifier; unknown ones are left pending so the background cron job has
real work to show.
"""

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Category, Transaction, TransactionStatus, User
from app.security import hash_password
from app.services.categorizer import classify_merchant, ensure_default_categories

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"

# (merchant, description, amount) — 10 merchants per month for 3 months
KNOWN = [
    ("Starbucks", "Morning coffee", 5.60),
    ("Whole Foods", "Weekly groceries", 78.40),
    ("Netflix", "Monthly subscription", 15.49),
    ("Uber", "Ride to office", 12.30),
    ("Shell Gas", "Fuel top-up", 45.00),
    ("Amazon", "Household items", 32.99),
    ("Planet Fitness", "Gym membership", 25.00),
    ("Comcast", "Internet bill", 60.00),
    ("Cinemark", "Movie tickets", 24.00),
    ("CVS Pharmacy", "Vitamins", 18.75),
]

UNKNOWN = [
    ("Ferris Market", "Fresh produce stand", 21.10),
    ("Loop Records", "Vinyl & merch", 48.00),
    ("Peak Fitness Club", "Monthly membership", 29.99),
]


def _month_starts(count: int) -> list[tuple[datetime, datetime]]:
    """Return (month_start, next_month_start) for the last `count` calendar months."""
    now = datetime.utcnow()
    starts: list[tuple[datetime, datetime]] = []
    y, m = now.year, now.month
    for _ in range(count):
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
        start = datetime(y, m, 1)
        next_start = datetime(y + 1, m, 1) if m == 12 else datetime(y, m + 1, 1)
        starts.append((start, next_start))
    return starts


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        ensure_default_categories(db)
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(email=DEMO_EMAIL, name="Demo User",
                        hashed_password=hash_password(DEMO_PASSWORD))
            db.add(user)
            db.commit()
            db.refresh(user)

        created = 0
        for month_start, next_start in _month_starts(3):
            rng = random.Random(42 + month_start.month)
            for merchant, description, amount in KNOWN:
                duplicate = db.query(Transaction).filter(
                    Transaction.user_id == user.id,
                    Transaction.merchant == merchant,
                    Transaction.created_at >= month_start.isoformat(),
                    Transaction.created_at < next_start.isoformat(),
                ).first()
                if duplicate:
                    continue
                day = rng.randint(1, 27)
                at = month_start + timedelta(days=day - 1) + timedelta(
                    hours=rng.randint(8, 21), minutes=rng.randint(0, 59)
                )
                tx = Transaction(
                    user_id=user.id, merchant=merchant, description=description,
                    amount=amount, currency="USD", status=TransactionStatus.pending,
                    created_at=at,
                )
                db.add(tx)
                db.flush()
                result = classify_merchant(db, tx.merchant, tx.description)
                tx.category_id = result.category_id
                tx.status = TransactionStatus.categorized
                tx.source = result.source
                tx.categorized_at = at
                created += 1

        # A few fresh unknown merchants left pending to showcase the cron job.
        now = datetime.utcnow()
        at = now.replace(hour=9, minute=30, second=0, microsecond=0) - timedelta(days=1)
        for merchant, description, amount in UNKNOWN:
            pending_exists = db.query(Transaction).filter(
                Transaction.user_id == user.id, Transaction.merchant == merchant,
            ).first()
            if pending_exists:
                continue
            db.add(Transaction(
                user_id=user.id, merchant=merchant, description=description,
                amount=amount, currency="USD", status=TransactionStatus.pending,
                created_at=at,
            ))
        db.commit()

        total = db.query(Transaction).filter(Transaction.user_id == user.id).count()
        pending = db.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.status == TransactionStatus.pending,
        ).count()
        print(f"Seeded demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"Transactions for this user: {total} "
              f"({created} categorized during seed, {pending} left pending for the cron job)")
        print("Categories:",
              ", ".join(c.name for c in db.query(Category).order_by(Category.name).all()))
    finally:
        db.close()


if __name__ == "__main__":
    seed()