from contextlib import contextmanager

import sqlalchemy
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Sequence
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import func


Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    password = Column(String)
    date_created = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())

#    transactions = relationship("Transaction", backref="user")

    def __repr__(self):
        return "<User(fullname='{0} {1}', password='{2}', created='{3}')>".format(
               self.first_name, self.last_name, self.password, self.date_created)


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, Sequence("file_id_seq"), primary_key=True)
    name = Column(String)
    data = Column(BYTEA)
    user_id = Column(Integer, ForeignKey("users.id"))
#    txn_id = Column(Integer, ForeignKey("transactions.id"))
    date_created = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())

    user = relationship("User", backref=backref("files", order_by=id), foreign_keys=[user_id])
#    transactions = relationship("Transaction", backref="file", foreign_keys=[txn_id])

    def __repr__(self):
        return "<File (name={0})>".format(self.name)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, Sequence("txn_id_seq"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    file_id = Column(Integer, ForeignKey("files.id"))
    date_created = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())


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
