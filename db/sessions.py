from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

Base.metadata.create_all(engine)

engine = create_engine("sqlite:///info.db", echo=True)
Session = sessionmaker(bind=engine)
