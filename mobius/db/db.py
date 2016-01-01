from contextlib import contextmanager
import enum

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy import Sequence
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import func


Base = declarative_base()


class ProviderID(enum.IntEnum):
    '''
    This list all commands that services can understand, and execute.
    '''
    SCULPTEO = 1


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="unique_email"),)

    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    email = Column(String)
    password = Column(String)
    date_created = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())

    transactions = relationship("Transaction")

    def __repr__(self):
        return "<User(email='{0}', password='{1}', created='{2}')>".format(
               self.email, self.password, self.date_created)


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, Sequence("file_id_seq"), primary_key=True)
    name = Column(String)
    data = Column(BYTEA)
    user_id = Column(Integer, ForeignKey("users.id"))
    date_created = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())

    user = relationship("User", backref=backref("files", order_by=id), foreign_keys=[user_id])
    transactions = relationship("Transaction")
    provider_info = relationship("ProviderInfo", lazy="joined")

    def __repr__(self):
        return "<File (name={0})>".format(self.name)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, Sequence("txn_id_seq"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    file_id = Column(Integer, ForeignKey("files.id"))
    date_created = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())


class ProviderInfo(Base):
    __tablename__ = "provider_infos"
    __table_args__ = (UniqueConstraint("mobius_id", "remote_id", name="unique_id"),)

    id = Column(Integer, Sequence("provider_info_seq"), primary_key=True)
    provider_id = Column(Integer)
    mobius_id = Column(Integer, ForeignKey("files.id"))
    remote_id = Column(String)
    date_created = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, Sequence("provider_info_seq"), primary_key=True)
    txn_id = Column(Integer, ForeignKey("transactions.id"))
    params = Column(String)


class DBHandle:
    '''
    Helper class to get access to the database.
    '''
    def __init__(self, url, verbose=False):
        '''
        Initialize a handle to the database

        @param url - the URL encodes the database type(postgresql, sqlite,
                     etc), user, password and database name.
        @param verbose - should the underlying SQL queries be echoed to log
                         output
        '''
        self._engine = create_engine(url, echo=verbose)
        Base.metadata.create_all(self._engine)
        self._session = scoped_session(sessionmaker(bind=self._engine))

    @contextmanager
    def session_scope(self):
        '''
        Provides a transactional scope around a series of operations.
        '''
        session = self._session()
        try:
            yield session
        except:
            session.rollback()
            raise
        finally:
            session.close()
