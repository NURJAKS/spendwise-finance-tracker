from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.schemas import GoalContribute, GoalCreate, GoalOut, GoalUpdate

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=List[GoalOut])
def list_goals(db: Session = Depends(get_db)):
    return crud.get_goals(db)


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalCreate, db: Session = Depends(get_db)):
    return crud.create_goal(db, data)


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, data: GoalUpdate, db: Session = Depends(get_db)):
    return crud.update_goal(db, goal_id, data)


@router.post("/{goal_id}/contribute", response_model=GoalOut)
def contribute_goal(
    goal_id: int, data: GoalContribute, db: Session = Depends(get_db)
):
    return crud.contribute_goal(db, goal_id, data)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    crud.delete_goal(db, goal_id)
    return None
