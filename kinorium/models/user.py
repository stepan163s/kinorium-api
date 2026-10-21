from typing import Any, Optional
from ..base import BaseModel
from ..utils import model

@model
class User(BaseModel):
    _field_aliases = {"id": "id_", "user_id": "id_", "image": "avatar"}

    id_: int
    name: str = ""
    avatar: str = ""
    client: Optional[Any] = None

    def __post_init__(self) -> None:
        self.id_ = int(self.id_)
        self._id_attrs = (self.id_,)

    def get_lists(self) -> Any:
        """
        Active method to retrieve lists metadata for this user.
        """
        return self.client.get_user_lists(user_id=self.id_)
