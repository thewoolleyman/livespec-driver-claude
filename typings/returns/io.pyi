from typing import Generic, TypeVar

_ValueType = TypeVar("_ValueType")
_ErrorType = TypeVar("_ErrorType")

class IO(Generic[_ValueType]):
    pass

class IOResult(Generic[_ValueType, _ErrorType]):
    def value_or(self, default_value: _ValueType) -> IO[_ValueType]: ...

class IOSuccess(IOResult[_ValueType, _ErrorType]):
    def __init__(self, inner_value: _ValueType) -> None: ...

class IOFailure(IOResult[_ValueType, _ErrorType]):
    def __init__(self, inner_value: _ErrorType) -> None: ...
