import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_URL = os.getenv('DATABASE_URL', 'sqlite:////tmp/clipra-next.db')
kwargs = {'connect_args': {'check_same_thread': False}} if DB_URL.startswith('sqlite') else {}
engine = create_engine(DB_URL, pool_pre_ping=True, **kwargs)
Session = sessionmaker(bind=engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass

def init_db():
    from . import models  # noqa
    Base.metadata.create_all(engine)