from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Column, event, inspect
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

    name = Column(sa.String)
    username = Column(sa.String, nullable=False)
    password = Column(sa.String, nullable=False)
    active = Column(sa.Boolean, default=True)

    @declared_attr
    def roles(self):
        return relationship('Role', secondary=user_role_rel, back_populates='users')

    @classmethod
    def authenticate(cls, db, username, password):
        user = db.query(cls).filter_by(username=username).first()
        if not user:
            return None
        if password != user.password:
            return False
        return user


class Role(Model):

    name = Column(sa.String, nullable=False)

    @declared_attr
    def perms(self):
        return relationship('Permission', cascade='all, delete-orphan')

    @declared_attr
    def users(self):
        return relationship('User', secondary=user_role_rel, back_populates='roles')


class Permission(Model):

    @declared_attr
    def roles(self):
        return Column(sa.Integer, sa.ForeignKey('role.id'))

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

    table_name = Column(sa.String)
    datetime = Column(sa.DateTime, default=datetime.now)
    operation = Column(sa.String)
    record_id = Column(sa.Integer)
    log_fields = relationship('UserActionLogField')


class UserActionLogField(Model):

    action_log_id = Column(sa.Integer, sa.ForeignKey('user_action_log.id'))
    field = Column(sa.String)
    old_value = Column(sa.String)
    new_value = Column(sa.String)


@event.listens_for(Model, 'after_insert', propagate=True)
def event_after_insert(mapper, connection, target):
    """ Record all operations about creating records,
     including all fields changes against tables
    """
    log_table = inspect(UserActionLog).mapped_table
    log_table_ins = log_table.insert().values(
                        table_name=mapper.mapped_table.name,
                        datetime=datetime.now(),
                        operation='create',
                        record_id=target.id
                    )
    result = connection.execute(log_table_ins)

    logfield_table = inspect(UserActionLogField).mapped_table
    tb_cols = {col.key for col in mapper.mapped_table.columns}
    for k, v in target.__dict__.items():
        if k in tb_cols and k != 'id':
            logfield_table_ins = logfield_table.insert().values(
                action_log_id=result.lastrowid,
                field=k,
                new_value=v
            )
            connection.execute(logfield_table_ins)
