from abc import ABC
from typing import Generic, Optional, Type, TypeVar, cast

T = TypeVar("T")


class SingleInheritanceRequired(Generic[T], ABC):
    """
    A singleton component is a component that only allow subclasses to be inherited.
    """

    @classmethod
    def check_only_one_subclass_allowed(cls) -> None:
        """
        Check if the subclass is allowed to be inherited.
        """
        class_dict: dict[str, Type[SingleInheritanceRequired[T]]] = {}
        for subclass in cls.__subclasses__():
            if subclass.__name__ in class_dict:
                continue
            class_dict[subclass.__name__] = subclass
        if len(class_dict) > 1:
            raise ValueError(
                f"Only one subclass is allowed for {cls.__name__}, but {len(class_dict)} subclasses: {[subclass.__name__ for subclass in class_dict.values()]} found"
            )

    @classmethod
    def get_subclass(cls) -> Optional[Type[T]]:
        """
        Get the subclass of the component.
        """
        cls.check_only_one_subclass_allowed()
        if len(cls.__subclasses__()) == 0:
            return
        return cast(Type[T], cls.__subclasses__()[0])
