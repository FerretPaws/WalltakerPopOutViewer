from dataclasses import dataclass

CLIENT_NAME = "WTPopOutViewer/1.0.7"


@dataclass(frozen=True)
class Service:
    key: str
    label: str
    host: str
    realtime: bool

    @property
    def base_url(self):
        return f"https://{self.host}"

    @property
    def cable_url(self):
        return f"wss://{self.host}/cable"


SERVICES = {
    "lycraon": Service("lycraon", "Walltaker Lycraon (walltaker.lycraon.online)", "walltaker.lycraon.online", realtime=True),
}
DEFAULT_SERVICE = "lycraon"
CUSTOM_SERVICE = "custom"


def normalize_host(text):
    text = (text or "").strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    return text.split("/", 1)[0].strip()


def get_service(key, custom_host="", custom_realtime=True):
    if key == CUSTOM_SERVICE:
        host = normalize_host(custom_host)
        if host:
            return Service(CUSTOM_SERVICE, f"Custom ({host})", host, realtime=custom_realtime)
    return SERVICES.get(key, SERVICES[DEFAULT_SERVICE])
