from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Column, event, inspect, events
from sqlalchemy.orm import relationship, validates, Query, events
from sqlalchemy.sql import select
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

    @classmethod
    def insert_by_conn(cls, conn, **kwargs):
        table = inspect(cls).persist_selectable
        table_ins = table.insert().values(**kwargs)
        result = conn.execute(table_ins)
        return result


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

    table = Column(sa.String)
    read = Column(sa.Boolean)
    create = Column(sa.Boolean)
    update = Column(sa.Boolean)
    delete = Column(sa.Boolean)

    @validates('model')
    def validate_model(self, key, value):
        assert value in [t.name for t in Base.metadata.tables]
        return value


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


@event.listens_for(Query, 'before_compile', retval=True)
def event_before_compile(query):
    conn = query.session.connection()

    for desc in query.column_descriptions:
        model = desc['type']

        _check_permission(conn, model, 'read')

        # query = query.filter(entity.active == True)
    return query


@event.listens_for(Model, 'after_insert', propagate=True)
def event_after_insert(mapper, connection, target):

    # Record all operations about creating records,
    # including all fields changes against tables
    result = UserActionLog.insert_by_conn(conn=connection, operation='create',
                                          table_name=mapper.persist_selectable.name,
                                          datetime=datetime.now(),
                                          record_id=target.id)

    tb_cols = {col.key for col in mapper.persist_selectable.columns}
    for k, v in target.__dict__.items():
        if k in tb_cols and k != 'id':
            UserActionLogField.insert_by_conn(conn=connection,
                                              action_log_id=result.lastrowid,
                                              field=k, new_value=v)


@event.listens_for(Model, 'after_update', propagate=True)
def event_after_update(mapper, connection, target):

    # Record all operations about updating records
    result = UserActionLog.insert_by_conn(conn=connection, operation='update',
                                          table_name=mapper.persist_selectable.name,
                                          datetime=datetime.now(),
                                          record_id=target.id)

    for attr in inspect(target).attrs:

        history = attr.load_history()
        if not history.has_changes():
            continue

        new_value = history.added[0]
        old_value = history.deleted[0]

        UserActionLogField.insert_by_conn(conn=connection,
                                          action_log_id=result.lastrowid,
                                          field=attr.key, old_value=old_value,
                                          new_value=new_value)


@event.listens_for(Model, 'after_delete', propagate=True)
def event_after_delete(mapper, connection, target):
    UserActionLog.insert_by_conn(conn=connection, operation='delete',
                                 table_name=mapper.persist_selectable.name,
                                 datetime=datetime.now(), record_id=target.id)


def _check_permission(conn, model: Model, operation):
    result = conn.execute(
        select([Permission])
        .where(
            Permission.table == model.__tablename__
        )
    )
    row = result.fetchone()
    if not row:
        raise PermissionError

    data = dict(row.items())
    if data[operation] is False:
        raise PermissionError
