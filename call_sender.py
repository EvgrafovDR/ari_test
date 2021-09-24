import ntpath
import os
import signal
import configparser
import socket
import string
import sys
import threading
import time
import random

from libraries.ari.ari import Ari


def get_random_string(length):
    # Random string with the combination of lower and upper case
    letters = string.ascii_letters
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


class SocketServer:

    def __init__(self):
        self._sock = None
        self._sock_type = socket.SOCK_DGRAM
        self._sock_family = socket.AF_INET
        self._host = "127.0.0.1"
        self._port = 55444
        self.opened = True
        self.connect()

    def connect(self):
        self._sock = socket.socket(self._sock_family, self._sock_type)
        self._sock.bind((self._host, self._port))

    def start(self):
        server_thread = threading.Thread(target=self.receive)
        server_thread.daemon = True
        server_thread.start()

    def receive(self):
        while self.opened:
            try:
                data, addr = self._sock.recvfrom(1024)
            except Exception as ex:
                if self.opened:
                    print("SOCKET ERROR")

    def close(self):
        """
        Closes the connection
        """
        if self.opened:
            self.opened = False
            self._close_socket()

    def _close_socket(self):
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except:
                pass

            try:
                self._sock.close()
            except:
                pass
            self._sock = None

    def terminate(self):
        self.close()


class Call:

    def __init__(self, channel, ari):
        self.channel = channel
        self.id = get_random_string(20)
        self.ari = ari
        self.stat = {
            "playback_started": 0,
            "playback_finished": 0,
            "answered": 0,
            "bridge_created": 0,
            "channel_added": 0,
            "finished": 0,
        }
        self.start_thread = threading.Thread(target=self._start)
        self.start_thread.daemon = True
        self.bridges = []
        self.snoop_spy_channel = None
        self.robot_channel = None
        self.media_bridge = None

    def playback_finished(self, ari, event, playback):
        print("playback finished")
        self.stat["playback_finished"] = 1
        self.channel.close()
        self.snoop_spy_channel.close()
        if self.robot_channel:
            self.robot_channel.close()
        for bridge in self.bridges:
            bridge.close()
        self.stat["finished"] = 1

    def start(self):
        self.start_thread.start()

    def create_sound_bridge(self):
        sound_bridge = self.ari.create_bridge()
        self.bridges.append(sound_bridge)
        self.stat["bridge_created"] = 1
        sound_bridge.add_channels([self.channel.id])
        self.stat["channel_added"] = 1
        return sound_bridge

    def start_recording(self, sound_bridge):
        sound_bridge.record("test_" + self.id)

    def start_playback(self, sound_bridge):
        file_name = "mid_sound"
        storage_path = os.path.dirname(os.path.abspath(__file__)) + '/sounds'
        sound = "%s/%s" % (storage_path, file_name)
        playback = sound_bridge.play("sound:%s" % sound)
        self.stat["playback_started"] = 1
        playback.append_callback("PlaybackFinished", self.playback_finished)

    def start_spy(self):
        media_bridge = self.ari.create_bridge()
        self.bridges.append(media_bridge)
        self.snoop_spy_channel = self.channel.snoop()
        return media_bridge

    def robot_channel_up(self, ari, event, channel):
        self.media_bridge.add_channels([self.snoop_spy_channel.id, channel.id])

    def start_robot_media(self, port):
        robot_channel_id = "robot_%s" % self.id
        self.ari.append_callback("StasisStart", self.robot_channel_up, robot_channel_id)
        self.robot_channel = self.ari.external_media(media_port=port, channel_id=robot_channel_id)

    def _start(self):
        self.channel.answer()
        self.stat["answered"] = 1
        sound_bridge = self.create_sound_bridge()
        self.start_recording(sound_bridge)
        self.media_bridge = self.start_spy()
        self.start_robot_media(55444)
        self.start_playback(sound_bridge)


class CallManager:

    def __init__(self, ari):
        self.ari = ari
        config_file = "configs/calls.ini"
        config_obj = configparser.ConfigParser()
        config_obj.readfp(open(config_file))
        self.calls_count = int(config_obj.get("calls", "count"))
        self.semaphore = threading.Semaphore(int(self.calls_count))
        self.driver = config_obj.get("calls", "driver")
        self.trunk = config_obj.get("calls", "trunk")
        self.phone = config_obj.get("calls", "phone")
        self.callerid = config_obj.get("calls", "callerid")
        self.calls = []
        self.sent_calls = 0
        self._terminate = False
        self.run_thread = None
        self.socket_server = SocketServer()
        self.socket_server.start()

    def start_call(self, ari, event):
        channel = event.channel
        if channel.protocol in ["PJSIP", "SIP"]:
            call = Call(channel, ari)
            self.calls.append(call)
            call.start()

    def end_call(self, ari, event):
        channel = event.channel
        if channel.protocol in ["PJSIP", "SIP"]:
            self.semaphore.release()

    def create_channel(self, channel_id, dial_string, caller_id):
        try:
            self.ari.create_channel(channel_id, dial_string, caller_id)
            self.sent_calls += 1
        except Exception as ex:
            print("create channel error: %s" % str(ex))
            self.semaphore.release()

    def send_call(self, channel_id, driver, trunk, phone, caller_id):
        if driver == "PJSIP":
            dial_string = "%s/%s@%s" % (driver, phone, trunk)
        else:
            dial_string = "%s/%s/%s" % (driver, trunk, phone)
        sending_thread = threading.Thread(target=self.create_channel,
                                          args=(channel_id,
                                                dial_string,
                                                caller_id))
        sending_thread.daemon = True
        self.semaphore.acquire()
        sending_thread.start()
        return sending_thread

    def run_async(self):
        self.run_thread = threading.Thread(target=self.run)
        self.run_thread.daemon = True
        self.run_thread.start()

    def run(self):
        self.ari.append_callback("StasisStart", self.start_call)
        self.ari.append_callback("ChannelDestroyed", self.end_call)
        call_num = 1
        while not self._terminate:
            self.send_call(call_num, self.driver, self.trunk, self.phone, self.callerid)
            call_num += 1
            
    def get_stat(self):
        result = {
            "playback_started": 0,
            "playback_finished": 0,
            "answered": 0,
            "bridge_created": 0,
            "channel_added": 0,
            "finished": 0,
        }
        for call in self.calls:
            for stat_key in result.keys():
                result[stat_key] += call.stat[stat_key]
        return result

    def terminate(self):
        self._terminate = True
        self.semaphore.release()
        if self.run_thread:
            self.run_thread.join()
        self.socket_server.terminate()

    def print_stat(self):
        stat = self.get_stat()
        print("sent_calls:\t%d" % self.sent_calls)
        for key, value in stat.items():
            print("%s:\t%d" % (key, value))


def main():
    global terminate
    terminate = False
    config_file = "configs/asterisk.ini"
    config_obj = configparser.ConfigParser()
    config_obj.readfp(open(config_file))
    ari_host = config_obj.get("ari", "host")
    ari_port = config_obj.get("ari", "port")
    ari_user = config_obj.get("ari", "username")
    ari_secret = config_obj.get("ari", "secret")
    ari_app = config_obj.get("ari", "app")
    ari_client = Ari("%s:%s" % (ari_host, ari_port), ari_user, ari_secret, ari_app)
    ari_client.run()
    call_manager = CallManager(ari_client)
    call_manager.run_async()
    while not terminate:
        time.sleep(3)
    call_manager.terminate()
    call_manager.print_stat()


def exit_gracefully(signum, frame):
    global terminate
    terminate = True


if __name__ == '__main__':
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
    main()
