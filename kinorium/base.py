from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

JSONType = Dict[str, Any]

PYTHON_RESERVED = frozenset({
    'type', 'from', 'import', 'class', 'return', 'pass',
    'in', 'is', 'format', 'filter', 'id', 'input', 'list',
    'dict', 'set', 'max', 'min', 'sum', 'map', 'zip',
})

Self = TypeVar('Self', bound='BaseModel')


def _recursive_to_dict(value: Any, for_request: bool) -> Any:
    if isinstance(value, BaseModel):
        return value.to_dict(for_request)
    if isinstance(value, list):
        return [_recursive_to_dict(v, for_request) for v in value]
    if isinstance(value, dict):
        return {k: _recursive_to_dict(v, for_request) for k, v in value.items()}
    return value


def _snake_to_camel(name: str) -> str:
    parts = name.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])


class BaseObject:
    @staticmethod
    def valid_client(client: Any) -> bool:
        return client is not None and not getattr(client, '_is_async', False)

    @staticmethod
    def valid_async_client(client: Any) -> bool:
        return client is not None and getattr(client, '_is_async', False)


class BaseModel(BaseObject):
    _id_attrs: tuple = ()

    @classmethod
    def is_dict_model_data(cls, data: Any) -> bool:
        return isinstance(data, dict) and bool(data)

    @classmethod
    def is_array_model_data(cls, data: Any) -> bool:
        return isinstance(data, list) and bool(data) and (len(data) == 0 or isinstance(data[0], dict))

    @classmethod
    def cleanup_data(cls, data: JSONType, client: Any) -> JSONType:
        known = {f.name for f in dataclasses.fields(cls)}
        known.discard('client')

        clean: JSONType = {}
        unknown: JSONType = {}

        for k, v in data.items():
            (clean if k in known else unknown)[k] = v

        if unknown and getattr(client, 'report_unknown_fields', False):
            logger.warning('%s: unknown API fields: %s', cls.__name__, list(unknown))

        return clean

    @classmethod
    def de_json(cls: Type[Self], data: Any, client: Any = None) -> Optional[Self]:
        if not cls.is_dict_model_data(data):
            return None
            
        cls_data = cls.cleanup_data(data, client)
        
        # Recursively deserialize fields representing other BaseModel classes
        for f in dataclasses.fields(cls):
            if f.name in cls_data:
                val = cls_data[f.name]
                field_type = f.type
                actual_type = cls._get_actual_type(field_type)
                
                if isinstance(actual_type, type) and issubclass(actual_type, BaseModel):
                    if isinstance(val, dict):
                        cls_data[f.name] = actual_type.de_json(val, client=client)
                elif cls._is_list_type(actual_type):
                    item_type = cls._get_list_item_type(actual_type)
                    if isinstance(item_type, type) and issubclass(item_type, BaseModel):
                        if isinstance(val, list):
                            cls_data[f.name] = item_type.de_list(val, client=client)
                            
        obj = cls(client=client, **cls_data)
        return obj

    @classmethod
    def de_list(cls: Type[Self], data: Any, client: Any = None) -> List[Self]:
        if not cls.is_array_model_data(data):
            return []
        items = [cls.de_json(item, client) for item in data]
        return [item for item in items if item is not None]

    def to_dict(self, for_request: bool = False) -> JSONType:
        raw = self.__dict__.copy()
        raw.pop('client', None)
        raw.pop('_id_attrs', None)

        if for_request:
            result: JSONType = {}
            for k, v in raw.items():
                camel = _snake_to_camel(k)
                # Strip trailing underscores from reserved words
                if camel.endswith("_") and camel[:-1] in ("id", "type", "from", "class", "def", "return", "in", "for", "while", "import"):
                    camel = camel[:-1]
                result[camel] = _recursive_to_dict(v, for_request)
            return result

        result = {}
        for k, v in raw.items():
            key = f'{k}_' if k in PYTHON_RESERVED else k
            result[key] = _recursive_to_dict(v, for_request)
        return result

    def to_json(self, for_request: bool = False) -> str:
        return json.dumps(self.to_dict(for_request), ensure_ascii=False)

    @staticmethod
    def _get_actual_type(t: Any) -> Any:
        if hasattr(t, "__origin__") and t.__origin__ is Union:
            for arg in t.__args__:
                if arg is not type(None):
                    return arg
        try:
            import types
            if hasattr(types, "UnionType") and isinstance(t, types.UnionType):
                for arg in t.__args__:
                    if arg is not type(None):
                        return arg
        except ImportError:
            pass
        return t

    @staticmethod
    def _is_list_type(t: Any) -> bool:
        if hasattr(t, "__origin__") and t.__origin__ is list:
            return True
        return False

    @staticmethod
    def _get_list_item_type(t: Any) -> Any:
        if hasattr(t, "__args__") and len(t.__args__) > 0:
            return t.__args__[0]
        return Any

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self._id_attrs == other._id_attrs
        return False

    def __hash__(self) -> int:
        frozen = tuple(
            frozenset(a) if isinstance(a, list) else a
            for a in self._id_attrs
        )
        return hash((self.__class__, frozen))

    def __repr__(self) -> str:
        try:
            fields = dataclasses.fields(self)
        except TypeError:
            return f'{self.__class__.__name__}()'
        attrs = ', '.join(
            f'{f.name}={getattr(self, f.name)!r}'
            for f in fields
            if f.name not in ('client', '_id_attrs')
        )
        return f'{self.__class__.__name__}({attrs})'
