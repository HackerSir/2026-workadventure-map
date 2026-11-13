import os
from datetime import datetime
from typing import Annotated
from uuid import UUID

import models
from database import SessionLocal, engine
from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import jwt

# Signs the prize key players paste into the form. It must stay out of the repository, which is
# public: anyone holding it could forge a key without playing.
JWT_SECRET = os.environ["HS_JWT_SECRET"]

# The prize form, with {token} where the prefilled key goes. Not secret, so it has a default.
REDEEM_FORM_URL = os.environ.get(
    "HS_REDEEM_FORM_URL",
    "https://docs.google.com/forms/d/e/1FAIpQLSdki3pmDTnUCt5vRMmDEPu1rUw36KZr9SQlm6KbJueK62uoNQ/viewform?usp=pp_url&entry.1520584581={token}",
)

models.Base.metadata.create_all(bind=engine)

# create_all does not add columns to an existing table, so add the office column by hand once.
with engine.begin() as connection:
    columns = [row[1] for row in connection.exec_driver_sql("PRAGMA table_info(states)")]
    if "office_finished_at" not in columns:
        connection.exec_driver_sql("ALTER TABLE states ADD COLUMN office_finished_at DATETIME")

app = FastAPI()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:5173",
    "https://hackersir.org",
    "https://town.hackersir.org",
    "https://townbeta.hackersir.org",
    "https://play.workadventu.re",
    "null",  # iframe
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index():
    return {"message": "Hello World"}


@app.get("/{uuid}/state")
async def get_state(
    uuid: UUID,
    user_agent: Annotated[str | None, Header()] = None,
    cf_connecting_ip: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        state = models.State(id=uuid.hex)
        db.add(state)

    # update user agent and ip
    state.user_agent = user_agent
    state.last_ip = cf_connecting_ip

    db.commit()

    return {
        "success": True,
        "kahoot_corrects": state.kahoot_corrects or [],
        "kahoot_kick_count": state.kahoot_kick_count or 0,
        "kahoot_finished_at": state.kahoot_finished_at,
        "cardgame_finished_at": state.cardgame_finished_at,
        "sheepwall_finished_at": state.sheepwall_finished_at,
        "cryptogame_finished_at": state.cryptogame_finished_at,
        "office_finished_at": state.office_finished_at,
    }


@app.post("/{uuid}/kahoot/finish")
async def kahoot_finish(
    uuid: UUID,
    corrects: list[int] = Body(..., embed=True, max_length=20, min_length=3),
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        raise HTTPException(status_code=404, detail="找不到玩家進度")

    state.kahoot_corrects = corrects
    state.kahoot_finished_at = datetime.now()

    db.commit()

    return {"success": True}


@app.post("/{uuid}/kahoot/kick")
async def kahoot_kick(
    uuid: UUID,
    question: int = Body(..., embed=True, ge=0),
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        raise HTTPException(status_code=404, detail="找不到玩家進度")

    state.kahoot_kick_count += 1

    db.commit()

    return {"success": True}


@app.post("/{uuid}/cardgame/finish")
async def cardgame_finish(
    uuid: UUID,
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        raise HTTPException(status_code=404, detail="找不到玩家進度")

    state.cardgame_finished_at = datetime.now()

    db.commit()

    return {"success": True}


@app.post("/{uuid}/sheepwall/finish")
async def sheepwall_finish(
    uuid: UUID,
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        raise HTTPException(status_code=404, detail="找不到玩家進度")

    state.sheepwall_finished_at = datetime.now()

    db.commit()

    return {"success": True}


@app.post("/{uuid}/cryptogame/finish")
async def cryptogame_finish(
    uuid: UUID,
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        raise HTTPException(status_code=404, detail="找不到玩家進度")

    state.cryptogame_finished_at = datetime.now()

    db.commit()

    return {"success": True}


@app.post("/{uuid}/office/finish")
async def office_finish(
    uuid: UUID,
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        raise HTTPException(status_code=404, detail="找不到玩家進度")

    state.office_finished_at = datetime.now()

    db.commit()

    return {"success": True}


@app.post("/{uuid}/redeem")
async def redeem(
    uuid: UUID,
    db: Session = Depends(get_db),
):
    state = db.query(models.State).filter(models.State.id == uuid.hex).first()

    if state is None:
        raise HTTPException(status_code=404, detail="找不到玩家進度")

    if state.redeemed_at:
        raise HTTPException(status_code=400, detail="你已經領過獎勵了 😡")

    stage_not_finished = []
    if not state.kahoot_finished_at:
        stage_not_finished.append("解謎屋")

    if not state.cardgame_finished_at:
        stage_not_finished.append("翻牌遊戲")

    if not state.sheepwall_finished_at:
        stage_not_finished.append("腳捲綿羊牆")

    if not state.cryptogame_finished_at:
        stage_not_finished.append("密碼學遊戲")

    if not state.office_finished_at:
        stage_not_finished.append("辦公室找碴")

    if len(stage_not_finished) > 0:
        raise HTTPException(
            status_code=400,
            detail="你還沒完成以下關卡: " + ", ".join(stage_not_finished),
        )

    state.redeemed_at = datetime.now()

    db.commit()

    token = jwt.encode(state.dict(), JWT_SECRET, algorithm="HS256")

    return {
        "success": True,
        "url": REDEEM_FORM_URL.format(token=token),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
