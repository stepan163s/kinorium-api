import dataclasses
from typing import Type, TypeVar

try:
    from typing import dataclass_transform  # Python 3.12+
except ImportError:
    try:
        from typing_extensions import dataclass_transform  # type: ignore[no-redef]
    except ImportError:
        # Fallback for older python/typing versions if typing_extensions is absent
        def dataclass_transform(*args, **kwargs):
            return lambda x: x

T = TypeVar('T')


@dataclass_transform()
def model(cls: Type[T]) -> Type[T]:
    """Decorator for model classes.

    Equivalent to @dataclass(eq=False, repr=False):
      - eq=False   → uses custom __eq__ / __hash__ via _id_attrs
      - repr=False → uses custom __repr__ from BaseModel
    """
    return dataclasses.dataclass(eq=False, repr=False)(cls)  # type: ignore[return-value]
