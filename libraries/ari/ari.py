import base64
import json
import queue
import sys
import time
import urllib.parse

import websocket
import threading
import http.client
import logging

from . import models
from . import events

logging.basicConfig(format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG)


class Ari:
    """
    Asterisk REST interface library
    If you want to add new action you can check it on
    https://wiki.asterisk.org/wiki/display/AST/Asterisk+16+ARI

    If you want to add new event handler you can find all events in events.json
    """

    RETRY_TIMEOUT = 1
    MAX_RETRIES = 10
    # If you want to add new event handler - you have to first add it here
    AVAILABLE_EVENTS = [
            "StasisStart",
            "Dial",
            "ChannelDestroyed",
            "StasisEnd",
            "PlaybackFinished",
            "PlaybackStarted",
            "ChannelCreated",
            "ChannelDtmfReceived"
        ]

    def __init__(self, url, user, password, app, event_callbacks={}):
        self.url = url
        self.user = user
        self.password = password
        self.app = app
        self._opened = False
        self._closed = False
        self._run_thread = None
        self._cb_thread = None
        self._allowed_events = set()
        self._cb_queue = queue.Queue()
        for event in event_callbacks:
            self.add_filter(event)
        for event in self.AVAILABLE_EVENTS:
            self.add_filter(event)
        self._event_callbacks = event_callbacks
        self._models_callbacks = {}
        self._callback_cs = threading.Lock()
        self.models = {"Channel": {},
                       "Bridge": {},
                       "Playback": {}}
        for model in self.models.keys():
            cls = getattr(models, model)
            for event in cls.finish_events:
                self.add_filter(event)
        self._auth_header = "Basic %s" % (base64.b64encode(
            ("%s:%s" % (self.user, self.password)).encode()).decode())
        self._ws = None
        self.ws_running = False

    def add_filter(self, event):
        self._allowed_events.add(event)

    def get_model(self, name, model_id):
        if model_id in self.models[name].keys():
            return self.models[name][model_id]
        else:
            return None

    def append_model(self, name, model):
        if self.ws_running:
            self.models[name][model.id] = model

    def remove_model(self, name, model_id):
        if model_id in self.models[name].keys():
            self.models[name].pop(model_id, None)
        event_keys = list(self._models_callbacks.keys())
        for event in event_keys:
            if model_id in self._models_callbacks[event].keys():
                self._models_callbacks[event].pop(model_id, None)

    def clear_models(self, event):
        models_name = self.models.keys()
        for model in models_name:
            cls = getattr(models, model)
            if event.type in cls.finish_events:
                fields = cls.finish_events[event.type]
                for field in fields:
                    obj = getattr(event, field)
                    self.remove_model(obj.__class__.__name__, obj.id)

    def append_callback(self, event, func, model_id=None):
        self.add_filter(event)
        with self._callback_cs:
            if model_id is None:
                if event not in self._event_callbacks.keys():
                    self._event_callbacks[event] = []
                if func not in self._event_callbacks[event]:
                    self._event_callbacks[event].append(func)
            else:
                if event not in self._models_callbacks.keys():
                    self._models_callbacks[event] = {}
                if model_id not in self._models_callbacks[event].keys():
                    self._models_callbacks[event][model_id] = []
                if func not in self._models_callbacks[event][model_id]:
                    self._models_callbacks[event][model_id].append(func)

    def remove_event_callback(self, event, func):
        if event in self._event_callbacks.keys() and func in self._event_callbacks[event]:
            self._event_callbacks[event].remove(func)

    def terminate(self):
        self.close()
        self.join_threads()

    def close(self):
        self.ws_running = False
        self._closed = True
        if self._ws is not None:
            self._ws.close()

    def join_threads(self):
        if self._run_thread is not None:
            logging.debug("wait for ari WS stop")
            self._run_thread.join()
            logging.debug("ari WS closed")
        self._cb_queue.put(None)
        if self._cb_thread is not None:
            logging.debug("wait for queue thread stop")
            self._cb_thread.join()
            logging.debug("queue thread stopped")

    def run(self):
        self.ws_running = True
        self._run_thread = threading.Thread(target=self._run)
        self._run_thread.daemon = True
        self._run_thread.start()
        self._cb_thread = threading.Thread(target=self._cb_sender)
        self._cb_thread.daemon = True
        self._cb_thread.start()

    def _run(self):
        self._ws = websocket.WebSocketApp("ws://%s/ari/events?app=%s" % (self.url, self.app),
                                          on_message=self.on_message,
                                          on_error=self.on_error,
                                          on_close=self.on_close,
                                          on_open=self.on_open,
                                          header=["Authorization: %s" % self._auth_header])
        logging.info("start ari websocket")
        while not self._closed:
            logging.info("start running websocket")
            self._ws.run_forever()
            if not self._closed:
                logging.error("websocket stop running")
                time.sleep(5)

    def _cb_sender(self):
        terminated = False
        while not terminated:
            item = self._cb_queue.get()
            if item is None:
                terminated = True
                logging.info("ari queue handler terminated")
                if not self._closed:
                    logging.error("ari queue handler terminated unexpectedly")
            else:
                self.send_callback(item)

    def on_message(self, ws, message):
        data = json.loads(message)
        logging.debug("Received event %s with payload: %s" % (data["type"], json.dumps(data, indent=4)))
        if data["type"] in self._allowed_events:
            if hasattr(events, data["type"]):
                event = self.create_event(data)
                self._cb_queue.put(event)

    def on_error(self, ws, error):
        if not self._closed:
            logging.error("WebSocket app error on close: %s" % error)

    def on_close(self, ws):
        if not self._closed:
            logging.error("WebSocket app closed")

    def on_open(self, ws):
        self._opened = True
        self.filter_events(self.AVAILABLE_EVENTS)

    def create_event(self, data):
        event = getattr(events, data["type"])(self, data)
        return event

    def send_callback(self, event):
        try:
            class_name = event.type
            logging.debug("start sending callbacks for %s" % class_name)
            if class_name in self._event_callbacks.keys():
                # I made this tmp because this array may changing in another thread
                tmp_callbacks = self._event_callbacks[class_name][:]
                for cb in tmp_callbacks:
                    cb(self, event)
            for model in self.models.keys():
                model_cls = getattr(models, model)
                if class_name in model_cls.related_events.keys():
                    fields = model_cls.related_events[class_name]
                    for field in fields:
                        obj = getattr(event, field)
                        if obj is not None:
                            obj.callback(self, event)
            logging.debug("finish sending callbacks for %s" % class_name)
            self.clear_models(event)
        except Exception as ex:
            logging.error("Error on send callback %s" % str(ex))

    def send_request(self, method, uri, params=None, body=None):
        if params is not None:
            params = urllib.parse.urlencode(params)
            uri = "%s?%s" % (uri, params)
        try:
            connection = http.client.HTTPConnection(self.url, timeout=10)
            connection.request(method, uri,
                               headers={"Authorization": self._auth_header, "Content-Type": "application/json"},
                               body=body)
            res = connection.getresponse()
            data = res.read().decode()
        except Exception as ex:
            logging.error("send request %s error in line %s: %s" % (uri, str(sys.exc_info()[-1].tb_lineno), str(ex)))
            raise ex
        if len(data) > 0 and (res.status == 200 or res.status == 201):
            result = json.loads(data)
            logging.debug("Response from %s: %s" % (uri, data))
            return result
        else:
            logging.debug("Response status from %s: %s %s %s" % (uri, res.status, res.reason, data))
            if res.status == 500:
                raise Exception("Response status from %s: %s %s %s" % (uri, res.status, res.reason, data))
            else:
                return

    def channels(self):
        response = self.send_request("GET", '/ari/channels')
        return response

    def create_channel(self, channel_id, endpoint, caller_id, variables={}, timeout=30):
        data = {
            "endpoint": endpoint,
            "app": self.app,
            "callerId": caller_id,
            "timeout": timeout
        }
        body = json.dumps({
            "variables": variables
        })
        response = self.send_request("POST", '/ari/channels/%s' % channel_id, data, body)
        channel = models.Channel.get_or_create(self, response)
        return channel

    def record_channel(self, channel_id, record_name, record_format="wav"):
        data = {"name": record_name, "format": record_format}
        response = self.send_request("POST", '/ari/channels/%s/record' % channel_id, data)
        return response

    def play_channel(self, channel_id, media):
        data = {"media": media}
        response = self.send_request("POST", '/ari/channels/%s/play' % channel_id, data)
        playback = models.Playback.get_or_create(self, response)
        return playback

    def ring_channel(self, channel_id):
        """
        :param channel_id: string
        :return: void
        """
        self.send_request("POST", "/ari/channels/%s/ring" % channel_id)

    def stop_ring_channel(self, channel_id):
        """
        :param channel_id: string
        :return: void
        """
        self.send_request("DELETE", "/ari/channels/%s/ring" % channel_id)

    def close_channel(self, channel_id):
        response = self.send_request("DELETE", '/ari/channels/%s' % channel_id)
        return response

    def external_media(self, media_port=56432, media_host="127.0.0.1", media_format="slin16", channel_id=None):
        data = {
            "external_host": "%s:%d" % (media_host, media_port),
            "app": self.app,
            "format": media_format
        }
        if channel_id is not None:
            data["channelId"] = channel_id
        response = self.send_request("POST", '/ari/channels/externalMedia', data)
        channel = models.Channel.get_or_create(self, response)
        return channel

    def start_snoop(self, channel_id, type='spy', direction="in"):
        data = {
            "app": self.app,
            type: direction
        }
        response = self.send_request("POST", '/ari/channels/%s/snoop' % channel_id, data)
        if response is None:
            return None
        channel = models.Channel.get_or_create(self, response)
        return channel

    def answer(self, channel_id):
        response = self.send_request("POST", '/ari/channels/%s/answer' % channel_id)
        return response

    def bridges(self):
        response = self.send_request("GET", '/ari/bridges')
        return response

    def close_bridge(self, bridge_id):
        response = self.send_request("DELETE", '/ari/bridges/%s' % bridge_id)
        return response

    def create_bridge(self):
        response = self.send_request("POST", '/ari/bridges')
        bridge = models.Bridge.get_or_create(self, response)
        return bridge

    def moh_bridge(self, bridge_id, moh):
        data = {"mohClass": moh}
        response = self.send_request("POST", "/ari/bridges/%s/moh" % bridge_id, data)
        return response

    def stop_moh_bridge(self, bridge_id):
        response = self.send_request("DELETE", "/ari/bridges/%s/moh" % bridge_id)
        return response

    def add_to_bridge(self, bridge_id, channels):
        data = {"channel": ",".join(channels)}
        response = self.send_request("POST", '/ari/bridges/%s/addChannel' % bridge_id, data)
        return response

    def remove_from_bridge(self, bridge_id, channels):
        data = {"channel": ",".join(channels)}
        response = self.send_request("POST", '/ari/bridges/%s/removeChannel' % bridge_id, data)
        return response

    def record_bridge(self, bridge_id, record_name, record_format="wav"):
        data = {"name": record_name, "format": record_format}
        response = self.send_request("POST", '/ari/bridges/%s/record' % bridge_id, data)
        return response

    def play_bridge(self, bridge_id, media):
        data = {"media": media}
        response = self.send_request("POST", '/ari/bridges/%s/play' % bridge_id, data)
        playback = models.Playback.get_or_create(self, response)
        return playback

    def play_silence(self, bridge_id, seconds):
        data = {"media": "sound:silence/%d" % int(seconds)}
        response = self.send_request("POST", '/ari/bridges/%s/play' % bridge_id, data)
        playback = models.Playback.get_or_create(self, response)
        return playback

    def close_playback(self, playback_id):
        self.send_request("DELETE", "/ari/playbacks/%s" % playback_id)

    def control_playback(self, playback_id, operation):
        """
        :param playback_id: string
        :param operation: List["restart", "pause", "unpause", "reverse", "forward"]
        :return: void
        """
        data = {"operation": operation}
        self.send_request("POST", "/ari/playbacks/%s/control" % playback_id, data)

    def filter_events(self, events):
        data = []
        for event in events:
            data.append({"type": event})
        body = json.dumps({
            "allowed": data
        })
        self.send_request("PUT", "/ari/applications/%s/eventFilter" % self.app, None, body)

    def list_apps(self):
        response = self.send_request("GET", "/ari/applications")
        return response
