from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.declarative import as_declarative, declared_attr


@as_declarative()
class Base:
    @declared_attr
    def __tablename__(cls):
        """ Create ``table_name`` automatically by class name
        example:
            class DemoModel's __tablename__ is 'demo_model'
        """
        res = []
        res.append(cls.__name__[0].lower())
        for c in cls.__name__[1:]:
            if c.isupper():
                res.append('_')
            res.append(c.lower())
        return ''.join(res)

    id = Column(sa.Integer, primary_key=True)

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"


Model = Base


user_role_rel = sa.Table(
    'user_role_rel', Base.metadata,
    Column('user_id', sa.ForeignKey('user.id'), primary_key=True),
    Column('role_id', sa.ForeignKey('role.id'), primary_key=True),
)


class User(Model):
    __abstract__ = True

    name = Column(sa.String)
    username = Column(sa.String, nullable=False)
    password = Column(sa.String, nullable=False)
    active = Column(sa.Boolean, default=True)
    roles = relationship('Role', secondary=user_role_rel, back_populates='users')

    @classmethod
    def authenticate(cls, db, username, password):
        user = db.query(cls).filter_by(username=username).first()
        if not user:
            return None
        if password != user.password:
            return False
        return user


class Role(Model):
    __abstract__ = True

    name = Column(sa.String, nullable=False)
    perms = relationship('Permission', cascade='all, delete-orphan')
    users = relationship('User', secondary=user_role_rel, back_populates='roles')


class Permission(Model):
    __abstract__ = True

    model = Column(sa.String)
    read_perm = Column(sa.Boolean)
    create_perm = Column(sa.Boolean)
    update_perm = Column(sa.Boolean)
    delete_perm = Column(sa.Boolean)

    @validates('model')
    def validate_model(self, key, name):
        assert name in [t.name for t in Base.metadata.tables]
        return name


class UserActionLog(Model):
    __abstract__ = True

    user_id = Column(sa.Integer, sa.ForeignKey('user.id'))
    user = relationship('User')
    datetime = Column(sa.DateTime, default=datetime.now)
    operation = Column(sa.String)
