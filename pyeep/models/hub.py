import pydantic


class HubConnectInfo(pydantic.BaseModel):
    """Information that clients can use to connect to the hub."""

    #: Hostname
    host: str
    #: Port
    port: int
    #: API token
    token: str

    def get_baseurl(self) -> str:
        return f"http://{self.host}:{self.port}"
