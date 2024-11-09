import shelve

class SettingsManager:
    def __init__(self):
        self.settings_file = "walltaker_settings"

    def save_settings(self, link_id, api_key, polling_delay, popout_size, notif_vol, auto_download, fade_out, fade_out_number):
        with shelve.open(self.settings_file) as settings:
            settings["link_id"] = link_id
            settings["api_key"] = api_key
            settings["polling_delay"] = polling_delay
            settings["popout_size"] = popout_size
            settings["notif_vol"] = notif_vol
            settings["auto_download"] = auto_download
            settings["fade_out"] = fade_out
            settings["fade_out_number"] = fade_out_number

    def load_settings(self):
        with shelve.open(self.settings_file) as settings:
            return {
                "link_id": settings.get("link_id", ""),
                "api_key": settings.get("api_key", ""),
                "polling_delay": settings.get("polling_delay", 0),
                "popout_size": settings.get("popout_size", 0),
                "notif_vol": settings.get("notif_vol", 0),
                "auto_download": settings.get("auto_download", False),
                "fade_out": settings.get("fade_out", False),
                "fade_out_number": settings.get("fade_out_number", 0)
            }