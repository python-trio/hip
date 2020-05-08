from abc import abstractmethod, ABC
from ssl import SSLContext
from typing import Optional, Tuple, Iterable, Union, Any, Dict, Callable, Awaitable


class AsyncBackend(ABC):
    @abstractmethod
    async def connect(
        self,
        host: str,
        port: int,
        connect_timeout: Optional[float],
        source_address: Optional[Tuple[str, int]] = None,
        socket_options: Optional[Iterable[Tuple[int, int, int]]] = None,
    ) -> "AsyncSocket":
        raise NotImplementedError()


class AsyncSocket(ABC):
    @abstractmethod
    async def start_tls(
        self, server_hostname: Optional[str], ssl_context: SSLContext
    ) -> "AsyncSocket":
        raise NotImplementedError()

    @abstractmethod
    def getpeercert(self, binary_form: bool = False) -> Union[bytes, Dict[str, Any]]:
        raise NotImplementedError()

    @abstractmethod
    async def receive_some(self, read_timeout: Optional[float]) -> bytes:
        raise NotImplementedError()

    @abstractmethod
    async def send_and_receive_for_a_while(
        self,
        produce_bytes: Callable[[], Awaitable[bytes]],
        consume_bytes: Callable[[bytes], None],
        read_timeout: Optional[float],
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    def forceful_close(self):
        raise NotImplementedError()

    @abstractmethod
    def is_readable(self) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def set_readable_watch_state(self, enabled: bool) -> None:
        raise NotImplementedError()
