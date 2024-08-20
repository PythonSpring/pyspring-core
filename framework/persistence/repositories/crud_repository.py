from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
)
from uuid import UUID

from loguru import logger
from sqlalchemy import Select
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import Select, SelectOfScalar

from framework.persistence.core.py_spring_model import session_auto_commit
from framework.persistence.repositories.repository_base import RepositoryBase

T = TypeVar("T", bound=SQLModel)
ID = TypeVar("ID", UUID, int)


class CrudRepository(RepositoryBase, Generic[ID, T]):
    """
    A CRUD (Create, Read, Update, Delete) repository implementation that provides common database operations for a single SQLModel entity.
    
    This repository is useful when you only need basic CRUD operations on a single database table. 
    For more complex scenarios involving multiple tables, you should consider using the Unit of Work pattern provided by SQLModel.
    
    The repository provides the following methods:
    - `find_by_id`: Retrieve a single entity by its ID.
    - `find_all_by_ids`: Retrieve a list of entities by their IDs.
    - `find_all`: Retrieve all entities.
    - `save`: Save a single entity.
    - `save_all`: Save a list of entities.
    - `delete`: Delete a single entity.
    - `delete_all`: Delete a list of entities.
    - `delete_by_id`: Delete an entity by its ID.
    - `delete_all_by_ids`: Delete a list of entities by their IDs.
    - `upsert`: Perform an upsert operation (insert or update) on a single entity based on a set of query parameters.
    
    The repository uses the SQLModel library for interacting with the database and automatically handles session management and transaction handling.
    """
    def __init__(self) -> None:
        super().__init__()
        self.id_type, self.model_class = self._get_model_id_type_with_class()

    @classmethod
    def _get_model_id_type_with_class(cls) -> tuple[Type[ID], Type[T]]:
        return get_args(tp=cls.__mro__[0].__orig_bases__[0])

    def _commit_operation_in_session(
        self,
        session_operation: Callable[[Session], None],
        session: Session,
    ) -> bool:
        try:
            session_operation(session)
            session.commit()
        except Exception as error:
            logger.error(error)
            session.rollback()
            raise error
        finally:
            session.close()

        return True
    
    def _find_by(
        self,
        statement: Union[Select, SelectOfScalar],
        session: Optional[Session] = None,
    ) -> Optional[T]:
        if session is None:
            session = self._create_session()

        return session.exec(statement).first()

    def _find_all_by(
        self,
        statement: Union[Select, SelectOfScalar],
        session: Optional[Session] = None,
    ) -> list[T]:
        if session is None:
            session = self._create_session()

        return list(session.exec(statement))

    def _create_session(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    def find_by_id(self, id: ID, session: Optional[Session] = None) -> Optional[T]:
        if session is None:
            session = self._create_session()

        statement = select(self.model_class).where(self.model_class.id == id)  # type: ignore
        return session.exec(statement).first()

    
    def find_all_by_ids(
        self, ids: list[ID], session: Optional[Session] = None
    ) -> list[T]:
        if session is None:
            session = self._create_session()
        statement = select(self.model_class).where(self.model_class.id.in_(ids))  # type: ignore
        return list(session.exec(statement).all())

    
    def find_all(self, session: Optional[Session] = None) -> list[T]:
        if session is None:
            session = self._create_session()
        statement = select(self.model_class)  # type: ignore
        return list(session.exec(statement).all())

    
    def save(self, entity: T, session: Optional[Session] = None) -> T:
        self._commit_operation_in_session(
            lambda session: session.add(entity), session or self._create_session()
        )
        return entity

    
    def save_all(
        self,
        entities: Iterable[T],
        session: Optional[Session] = None,
    ) -> bool:
        return self._commit_operation_in_session(
            lambda session: session.add_all(entities), session or self._create_session()
        )

    
    def delete(self, entity: T, session: Optional[Session] = None) -> bool:
        return self._commit_operation_in_session(
            lambda session: session.delete(entity), session or self._create_session()
        )

    @session_auto_commit
    def delete_all(
        self, entities: Iterable[T], session: Optional[Session] = None
    ) -> bool:
        session = session or self._create_session()
        for entity in entities:
            session.delete(entity)
        return True

    @session_auto_commit
    def delete_by_id(self, id: ID, session: Optional[Session] = None) -> bool:
        if session is None:
            session = self._create_session()

        entity = self.find_by_id(id, session)
        if entity is not None:
            return self.delete(entity, session)
        return False

    @session_auto_commit
    def delete_all_by_ids(
        self, ids: list[ID], session: Optional[Session] = None
    ) -> bool:
        if session is None:
            session = self._create_session()
        
        entities = self.find_all_by_ids(ids, session)
        for entity in entities:
            session.delete(entity)
        return True
    
    @session_auto_commit
    def upsert(self, entity: T, query_by: dict[str, Any],session: Optional[Session] = None) -> T:
        if session is None:
            session = self._create_session()
        # Check if the entity already exists in the database by its ID


        statement = select(self.model_class).filter_by(**query_by)  # type: ignore
        existing_entity = self._find_by(statement, session)
        if existing_entity is not None:
            # If the entity exists, update its attributes
            for key, value in entity.model_dump().items():
                setattr(existing_entity, key, value)
            session.add(existing_entity)
        else:
            # If the entity does not exist, insert it
            session.add(entity)
        return entity