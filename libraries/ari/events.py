from . import models


class Message(object):

    def __init__(self, ari, data):
        self._ari = ari
        self.type = data["type"]
        self.asterisk_id = data.get("asterisk_id", None)


class Event(Message):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.application = data["type"]
        self.timestamp = data["timestamp"]


class MissingParams(Message):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.params = data["params"]


class DeviceStateChanged(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.device_state = data["device_state"]


class PlaybackStarted(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.playback = models.Playback.get_or_create(ari, data["playback"])


class PlaybackContinuing(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.playback = models.Playback.get_or_create(ari, data["playback"])


class PlaybackFinished(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.playback = models.Playback.get_or_create(ari, data["playback"])


class RecordingStarted(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.recording = data["recording"]


class RecordingFinished(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.recording = data["recording"]


class RecordingFailed(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.recording = data["recording"]


class BridgeCreated(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.bridge = models.Bridge.get_or_create(ari, data["bridge"])


class BridgeDestroyed(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.bridge = models.Bridge.get_or_create(ari, data["bridge"])


class BridgeMerged(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.bridge = models.Bridge.get_or_create(ari, data["bridge"])
        self.bridge_from = models.Bridge.get_or_create(ari, data["bridge_from"])


class ChannelCreated(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelDestroyed(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.cause = data["cause"]
        self.cause_txt = data["cause_txt"]
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelEnteredBridge(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])
        self.bridge = models.Bridge.get_or_create(ari, data["bridge"])


class ChannelLeftBridge(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])
        self.bridge = models.Bridge.get_or_create(ari, data["bridge"])


class ChannelStateChange(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelDtmfReceived(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.digit = data["digit"]
        self.duration_ms = data["duration_ms"]
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelDialplan(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.dialplan_app = data["dialplan_app"]
        self.dialplan_app_data = data["dialplan_app_data"]
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelCallerId(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.caller_presentation = data["caller_presentation"]
        self.caller_presentation_txt = data["caller_presentation_txt"]
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelUserevent(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.eventname = data["eventname"]
        self.userevent = data["userevent"]
        self.endpoint = data.get("endpoint", None)
        self.channel = data.get("channel", None)
        self.bridge = data.get("bridge", None)
        if self.channel is not None:
            self.channel = models.Channel.get_or_create(ari, data["channel"])
        if self.bridge is not None:
            self.bridge = models.Bridge.get_or_create(ari, data["bridge"])


class ChannelHangupRequest(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        if "cause" in data:
            self.cause = data["cause"]
        if "soft" in data:
            self.soft = data.get("soft", None)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelVarset(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = data.get("channel", None)
        self.variable = data["variable"]
        self.value = data["value"]
        if self.channel is not None:
            self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelHold(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.musicclass = data.get("musicclass", None)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelUnhold(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelTalkingStarted(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelTalkingFinished(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.duration = data["duration"]
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ContactStatusChange(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.endpoint = data["endpoint"]
        self.contact_info = data["contact_info"]


class PeerStatusChange(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.endpoint = data["endpoint"]
        self.peer = data["peer"]


class EndpointStateChange(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.endpoint = data["endpoint"]


class Dial(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.caller = data.get("caller", None)
        self.forward = data.get("forward", None)
        self.forwarded = data.get("forwarded", None)
        self.dialstring = data.get("dialstring", None)
        self.dialstatus = data["dialstatus"]
        self.peer = models.Channel.get_or_create(ari, data["peer"])
        if self.caller is not None:
            self.caller = models.Channel.get_or_create(ari, data["caller"])
        if self.forwarded is not None:
            self.forwarded = models.Channel.get_or_create(ari, data["forwarded"])


class StasisEnd(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class StasisStart(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.replace_channel = data.get("replace_channel", None)
        self.args = data["args"]
        if self.replace_channel is not None:
            self.replace_channel = models.Channel.get_or_create(ari, self.replace_channel)
        self.channel = models.Channel.get_or_create(ari, data["channel"])


class ChannelConnectedLine(Event):

    def __init__(self, ari, data):
        super().__init__(ari, data)
        self.channel = models.Channel.get_or_create(ari, data["channel"])
