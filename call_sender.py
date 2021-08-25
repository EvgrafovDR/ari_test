import ntpath
import os
import signal
import configparser
import sys
import threading
import time

from libraries.ari.ari import Ari


class Call:

    def __init__(self, channel, ari):
        self.channel = channel
        self.ari = ari

    def playback_finished(self, ari, event, playback):
        print("playback finished")
        self.channel.close()

    def start(self):
        start_thread = threading.Thread(target=self.start_thread)
        start_thread.daemon = True
        start_thread.start()

    def start_thread(self):
        self.channel.answer()
        sound_bridge = self.ari.create_bridge()
        sound_bridge.add_channels([self.channel.id])
        file_name = "mid_sound"
        storage_path = os.path.dirname(os.path.abspath(__file__)) + '/sounds'
        sound = "%s/%s" % (storage_path, file_name)
        playback = sound_bridge.play("sound:%s" % sound)
        playback.append_callback("PlaybackFinished", self.playback_finished)


class CallManager:

    def __init__(self, ari):
        self.ari = ari
        config_file = "configs/calls.ini"
        config_obj = configparser.ConfigParser()
        config_obj.readfp(open(config_file))
        self.calls_count = int(config_obj.get("calls", "count"))
        self.driver = config_obj.get("calls", "driver")
        self.trunk = config_obj.get("calls", "trunk")
        self.phone = config_obj.get("calls", "phone")
        self.callerid = config_obj.get("calls", "callerid")

    def start_call(self, ari, event):
        channel = event.channel
        call = Call(channel, ari)
        call.start()

    def send_call(self, channel_id, driver, trunk, phone, caller_id):
        if driver == "PJSIP":
            dial_string = "%s/%s@%s" % (driver, phone, trunk)
        else:
            dial_string = "%s/%s/%s" % (driver, trunk, phone)
        sending_thread = threading.Thread(target=self.ari.create_channel,
                                          args=(channel_id,
                                                dial_string,
                                                caller_id))
        sending_thread.daemon = True
        sending_thread.start()
        return sending_thread

    def run(self):
        self.ari.append_callback("StasisStart", self.start_call)
        threads = []
        for i in range(1, self.calls_count):
            threads.append(self.send_call(i, self.driver, self.trunk, self.phone, self.callerid))
        for thread in threads:
            thread.join()


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
    call_manager.run()
    while not terminate:
        time.sleep(3)


def exit_gracefully(signum, frame):
    global terminate
    terminate = True


if __name__ == '__main__':
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
    main()
