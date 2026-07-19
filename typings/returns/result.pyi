from typing import Generic, TypeVar

_ValueType = TypeVar("_ValueType")
_ErrorType = TypeVar("_ErrorType")

class Result(Generic[_ValueType, _ErrorType]):
    def value_or(self, default_value: _ValueType) -> _ValueType: ...

class Success(Result[_ValueType, _ErrorType]):
    def __init__(self, inner_value: _ValueType) -> None: ...

class Failure(Result[_ValueType, _ErrorType]):
    def __init__(self, inner_value: _ErrorType) -> None: ...
