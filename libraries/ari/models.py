import json
import threading


class Model(object):

    related_events = {}
    finish_events = {}
    create_cs = threading.Lock()

    def __init__(self, ari, data):
        self._ari = ari
        self.data = data
        self.id = data["id"]
        self._event_callbacks = {}
        ari.append_model(self.__class__.__name__, self)

    @classmethod
    def get_or_create(cls, ari, data):
        name = cls.__name__
        with cls.create_cs:
            model = ari.get_model(name, data["id"])
            if model is not None:
                model.update_from_data(data)
                return model
            else:
                model = cls(ari, data)
                return model

    def update_from_data(self, data):
        self.data = data

    def as_string(self):
        return json.dumps(self.data)

    def callback(self, ari, event):
        if event.type in self._event_callbacks:
            # I made this tmp because this array may changing in another thread
            tmp_callbacks = self._event_callbacks[event.type][:]
            for cb in tmp_callbacks:
                cb(ari, event, self)

    def append_callback(self, event, func):
        self._ari.add_filter(event)
        if event not in self._event_callbacks.keys():
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(func)
        return True

    def remove_from_ari(self):
        self._ari.remove_model(self.__class__.__name__, self.id)


class Channel(Model):

    related_events = {"ChannelCreated": ["channel"],
                      "ChannelDestroyed": ["channel"],
                      "ChannelEnteredBridge": ["channel"],
                      "ChannelStateChange": ["channel"],
                      "ChannelLeftBridge": ["channel"],
                      "ChannelDtmfReceived": ["channel"],
                      "ChannelDialplan": ["channel"],
                      "ChannelCallerId": ["channel"],
                      "ChannelHangupRequest": ["channel"],
                      "ChannelVarset": ["channel"],
                      "ChannelHold": ["channel"],
                      "ChannelUnhold": ["channel"],
                      "ChannelTalkingStarted": ["channel"],
                      "ChannelTalkingFinished": ["channel"],
                      "Dial": ["caller", "peer", "forwarded"],
                      "StasisEnd": ["channel"],
                      "StasisStart": ["channel", "replace_channel"],
                      "ChannelConnectedLine": ["channel"],
                      }

    finish_events = {
        "ChannelDestroyed": ["channel"],
        "StasisEnd": ["channel"]
    }

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.name = data["name"]
        self.state = data["state"]
        self.caller = CallerID(data["caller"])
        self.connected = CallerID(data["connected"])
        self.creationtime = data["creationtime"]
        self.language = data["language"]
        self.dialplan = data["dialplan"]
        self.accountcode = data["accountcode"]
        self.channelvars = []
        if "channelvars" in data.keys():
            self.channelvars = data["channelvars"]
        self.protocol = self.name.split("/")[0]
        self.snoop_channels = []

    def update_from_data(self, data):
        super().update_from_data(data)
        self.state = data["state"]
        self.connected = CallerID(data["connected"])
        self.dialplan = data["dialplan"]
        self.accountcode = data["accountcode"]
        self.channelvars = []
        if "channelvars" in data.keys():
            self.channelvars = data["channelvars"]

    def record(self, record_name, record_format="wav"):
        self._ari.record_channel(self.id, record_name, record_format)

    def play(self, media):
        playback = self._ari.play_channel(self.id, media)
        return playback

    def close(self):
        self._ari.close_channel(self.id)

    def snoop(self):
        channel = self._ari.start_snoop(self.id, "spy", "in")
        if channel is not None:
            self.snoop_channels.append(channel)
        return channel

    def answer(self):
        self._ari.answer(self.id)

    def ring(self):
        self._ari.ring_channel(self.id)

    def stop_ring(self):
        self._ari.stop_ring_channel(self.id)


class CallerID:

    def __init__(self, data):
        self.name = data["name"]
        self.number = data["number"]


class Bridge(Model):

    related_events = {"BridgeCreated": ["bridge"],
                      "BridgeDestroyed": ["bridge"],
                      "BridgeMerged": ["bridge"],
                      "ChannelEnteredBridge": ["bridge"],
                      "ChannelLeftBridge": ["bridge"],
                      "ChannelUserevent": ["bridge"],
                      }

    finish_events = {
        "BridgeDestroyed": ["bridge"]
    }

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.technology = data["technology"]
        self.bridge_type = data["bridge_type"]
        self.bridge_class = data["bridge_class"]
        self.creator = data["creator"]
        self.name = data["name"]
        self.channels_id = data["channels"]
        self.creationtime = data["creationtime"]

    def update_from_data(self, data):
        super().update_from_data(data)
        self.channels_id = data["channels"]

    def add_channels(self, channels):
        self._ari.add_to_bridge(self.id, channels)

    def remove_channels(self, channels):
        self._ari.remove_from_bridge(self.id, channels)

    def record(self, record_name, record_format="wav"):
        self._ari.record_bridge(self.id, record_name, record_format)

    def moh(self, moh_class):
        self._ari.moh_bridge(self.id, moh_class)

    def stop_moh(self):
        self._ari.stop_moh_bridge(self.id)

    def play(self, media):
        playback = self._ari.play_bridge(self.id, media)
        return playback

    def play_silence(self, seconds):
        playback = self._ari.play_silence(self.id, seconds)
        return playback

    def close(self):
        self._ari.close_bridge(self.id)
        self.remove_from_ari()


class Playback(Model):

    related_events = {"PlaybackStarted": ["playback"],
                      "PlaybackContinuing": ["playback"],
                      "PlaybackFinished": ["playback"],
                      }

    finish_events = {
        "PlaybackFinished": ["playback"]
    }

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.media_uri = data["media_uri"]
        self.target_uri = data["target_uri"]
        self.language = data["language"]
        self.state = data["state"]

    def update_from_data(self, data):
        super().update_from_data(data)
        self.media_uri = data["media_uri"]
        self.target_uri = data["target_uri"]
        self.language = data["language"]
        self.state = data["state"]

    def close(self):
        self._ari.close_playback(self.id)
        self.remove_from_ari()

    def restart(self):
        self._ari.control_playback(self.id, "restart")

    def pause(self):
        self._ari.control_playback(self.id, "pause")

    def unpause(self):
        self._ari.control_playback(self.id, "unpause")

    def reverse(self):
        self._ari.control_playback(self.id, "reverse")

    def forward(self):
        self._ari.control_playback(self.id, "forward")