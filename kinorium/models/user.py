from typing import Any, Optional
from ..base import BaseModel
from ..utils import model

@model
class User(BaseModel):
    id_: int
    name: str = ""
    avatar: str = ""
    client: Optional[Any] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.id_,)

    def get_lists(self) -> Any:
        """
        Active method to retrieve lists metadata for this user.
        """
        return self.client.get_user_lists(user_id=self.id_)
