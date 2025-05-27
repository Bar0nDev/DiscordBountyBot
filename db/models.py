from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

class Missions(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    reward = Column(Integer)
    difficulty = Column(String)
    faction = Column(String)
    availability = Column(String)

class Bounties(Base):
    __tablename__ = "bounties"
    id = Column(Integer, primary_key=True)
    target = Column(String)
    description = Column(String)
    reward = Column(Integer)
    client = Column(String)

engine = create_engine("sqlite:///info.db", echo=True)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()
