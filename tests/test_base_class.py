import pytest
import sqlalchemy as sa

from samodel import Base


class Config:
    db_url = 'sqlite:///:memory:'


settings = Config()


@pytest.fixture(scope='module')
def conn():
    import sqlite3
    conn = sqlite3.connect(settings.db_url)
    return conn


@pytest.fixture()
def session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from samodel.model import Base
    engine = create_engine(settings.db_url)
    SessionLocal = sessionmaker(engine)

    Base.metadata.create_all()

    return SessionLocal()


@pytest.fixture(scope='module')
def DemoModel():
    class DemoModel(Base):
        name = sa.Column(sa.String)
    return DemoModel


def test_base_function(DemoModel):
    assert DemoModel.__tablename__ == 'demo_model'
    assert 'id' in DemoModel.__dict__

    demo = DemoModel(name='guido')
    assert repr(demo) == "<DemoModel(id=None)>"


def test_log_event(conn, session, DemoModel):
    demo = DemoModel(name='guido')
    session.add(demo)
    session.commit()

    with conn:
        conn.execute(f"select table_name, record_id, operation from {demo.__tablename__}")
        result = conn.fetchone()
    assert result[0]
