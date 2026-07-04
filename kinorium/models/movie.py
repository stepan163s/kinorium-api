from typing import List, Optional, Any
from ..base import BaseModel
from ..utils import model

@model
class Movie(BaseModel):
    id_: int
    title: str = ""
    genres: Optional[List[str]] = None
    year: int = 0
    client: Optional[Any] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.id_,)


@model
class UserList(BaseModel):
    ulist_id: int
    obj_type: str = ""
    title: str = ""
    special: str = ""
    client: Optional[Any] = None

    def __post_init__(self) -> None:
        self._id_attrs = (self.ulist_id,)

    def get_objects(self, page: int = 1, perpage: int = 50) -> Any:
        """
        Active method to retrieve movies in this list.
        """
        return self.client.get_user_list_objects(ulist_id=self.ulist_id, page=page, perpage=perpage)
