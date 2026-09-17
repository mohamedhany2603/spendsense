from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Category, Transaction, TransactionStatus, User
from ..schemas import (
    TransactionBulkCreate,
    TransactionCreate,
    TransactionOut,
    TransactionPatch,
)
from ..services.cache import invalidate_user_cache
from ..services.categorizer import classify_merchant

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _to_out(tx: Transaction) -> TransactionOut:
    return TransactionOut(
        id=tx.id,
        merchant=tx.merchant,
        description=tx.description,
        amount=tx.amount,
        currency=tx.currency,
        status=tx.status.value,
        source=tx.source.value if tx.source else None,
        category_id=tx.category_id,
        category_name=tx.category.name if tx.category else None,
        created_at=tx.created_at,
        categorized_at=tx.categorized_at,
    )


def _apply_category_if_needed(db: Session, tx: Transaction) -> None:
    """Categorize synchronously when the user didn't pass a category_id."""
    if tx.category_id is not None:
        tx.status = TransactionStatus.categorized
        tx.source = "manual"
        tx.categorized_at = datetime.utcnow()
        return
    if tx.status == TransactionStatus.categorized:
        return
    result = classify_merchant(db, tx.merchant, tx.description)
    tx.category_id = result.category_id
    tx.status = TransactionStatus.categorized
    tx.source = result.source
    tx.categorized_at = datetime.utcnow()


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionOut:
    if payload.category_id is not None:
        category = db.query(Category).filter(Category.id == payload.category_id).first()
        if category is None:
            raise HTTPException(status_code=422, detail="Unknown category_id")

    tx = Transaction(
        user_id=current_user.id,
        merchant=payload.merchant,
        description=payload.description,
        amount=payload.amount,
        currency=payload.currency,
        category_id=payload.category_id,
        status=TransactionStatus.pending,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    _apply_category_if_needed(db, tx)
    db.commit()
    db.refresh(tx)
    invalidate_user_cache(current_user.id)
    return _to_out(tx)


@router.post("/bulk", response_model=list[TransactionOut], status_code=status.HTTP_201_CREATED)
def create_bulk(
    payload: TransactionBulkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionOut]:
    txs = [
        Transaction(
            user_id=current_user.id,
            merchant=item.merchant,
            description=item.description,
            amount=item.amount,
            currency=item.currency,
            category_id=item.category_id,
            status=TransactionStatus.pending,
        )
        for item in payload.items
    ]
    db.add_all(txs)
    db.commit()
    for tx in txs:
        _apply_category_if_needed(db, tx)
        db.flush()
    db.commit()
    invalidate_user_cache(current_user.id)
    return [_to_out(tx) for tx in txs]


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    status_filter: TransactionStatus | None = Query(default=None, alias="status"),
    category_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionOut]:
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if status_filter is not None:
        query = query.filter(Transaction.status == status_filter)
    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)
    rows = query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()
    return [_to_out(tx) for tx in rows]


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionOut:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _to_out(tx)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def patch_transaction(
    transaction_id: int,
    payload: TransactionPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionOut:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if payload.category_id is not None:
        category = db.query(Category).filter(Category.id == payload.category_id).first()
        if category is None:
            raise HTTPException(status_code=422, detail="Unknown category_id")
        tx.category_id = payload.category_id
        tx.status = TransactionStatus.categorized
        tx.source = "manual"
        tx.categorized_at = datetime.utcnow()
    if payload.merchant is not None:
        tx.merchant = payload.merchant
    if payload.description is not None:
        tx.description = payload.description

    db.commit()
    db.refresh(tx)
    invalidate_user_cache(current_user.id)
    return _to_out(tx)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(tx)
    db.commit()
    invalidate_user_cache(current_user.id)