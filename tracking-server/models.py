from fastapi.encoders import jsonable_encoder
from database import Base
from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func


class State(Base):
    __tablename__ = "states"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    last_ip = Column(String)
    user_agent = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    redeemed_at = Column(DateTime(timezone=True), nullable=True)

    # kahoot
    kahoot_corrects = Column(JSON, default=[])
    kahoot_finished_at = Column(DateTime(timezone=True), nullable=True)
    kahoot_kick_count = Column(Integer, default=0)

    # card game
    cardgame_finished_at = Column(DateTime(timezone=True), nullable=True)

    # sheepwall
    sheepwall_finished_at = Column(DateTime(timezone=True), nullable=True)

    # crypto game
    cryptogame_finished_at = Column(DateTime(timezone=True), nullable=True)

    # office spot-the-flaws
    office_finished_at = Column(DateTime(timezone=True), nullable=True)

    def dict(self):
        return jsonable_encoder(
            {
                "id": self.id,
                "name": self.name,
                "last_ip": self.last_ip,
                "user_agent": self.user_agent,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "kahoot_corrects": self.kahoot_corrects,
                "kahoot_finished_at": self.kahoot_finished_at,
                "kahoot_kick_count": self.kahoot_kick_count,
                "cardgame_finished_at": self.cardgame_finished_at,
                "sheepwall_finished_at": self.sheepwall_finished_at,
                "cryptogame_finished_at": self.cryptogame_finished_at,
                "office_finished_at": self.office_finished_at,
            }
        )
