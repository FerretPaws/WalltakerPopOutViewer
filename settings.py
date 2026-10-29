import shelve

class SettingsManager:
    def __init__(self):
        self.settings_file = "walltaker_settings"

    def save_settings(self, link_id, api_key, polling_delay, popout_size, notif_vol, auto_download,     fade_out, fade_out_number, service="lycraon", custom_host="", custom_realtime=True, media_enabled=False, media_autoplay=True, media_mute=False, media_volume=50):
        with shelve.open(self.settings_file) as settings:
            settings["service"] = service
            settings["custom_host"] = custom_host
            settings["custom_realtime"] = custom_realtime
            settings["media_enabled"] = media_enabled
            settings["media_autoplay"] = media_autoplay
            settings["media_mute"] = media_mute
            settings["media_volume"] = media_volume
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
                "service": settings.get("service", "lycraon"),
                "custom_host": settings.get("custom_host", ""),
                "custom_realtime": settings.get("custom_realtime", True),
                "media_enabled": settings.get("media_enabled", False),
                "media_autoplay": settings.get("media_autoplay", True),
                "media_mute": settings.get("media_mute", False),
                "media_volume": settings.get("media_volume", 50),
                "link_id": settings.get("link_id", ""),
                "api_key": settings.get("api_key", ""),
                "polling_delay": settings.get("polling_delay", 0),
                "popout_size": settings.get("popout_size", 0),
                "notif_vol": settings.get("notif_vol", 0),
                "auto_download": settings.get("auto_download", False),
                "fade_out": settings.get("fade_out", False),
                "fade_out_number": settings.get("fade_out_number", 0)
            }