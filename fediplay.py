from os import environ, umask, chdir, mkdir, path
from subprocess import run
from threading import Thread, Lock

from lxml.etree import HTML
import mastodon
Mastodon = mastodon.Mastodon
from youtube_dl import YoutubeDL

from mpd import MPDClient

class Player(object):
    def __init__(self):
        pass

    def add(self, url):
        raise NotImplemented("Add method not implemented (you probably want to fix this if you want it to do *anything*")

class RadioPlayer(Player):
    def __init__(self, settings):
        if "host" not in settings:
            raise ValueError("player_settings.host parameter is required!")
        self.host = settings["host"]
        self.port = settings.setdefault("port", 6600)
        self.client = MPDClient()
        self.clientlock = Lock()

    def add_to_client(self, filename):
        output_file = "{}.mp3".format(filename)
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "panic", "-i", filename, output_file])
    
        with self.clientlock:
            try:
                self.client.add("file://{}".format(path.abspath(output_file)))
            except:
                self.client.connect(self.host, self.port)
                self.client.add("file://{}".format(path.abspath(output_file)))
            print("Added {} to queue".format(output_file))

    def ph(self, progress):
        if progress["status"] == "finished":
            self.add_to_client(progress["filename"])

    def download(self, url):
        options = {
                "format": "mp3/mp4",
                "progress_hooks": [self.ph],
                "outtmpl": "./music/%(title)s.%(ext)s"
            }
        
        with YoutubeDL(options) as downloader:
            downloader.download([url])

    def add(self, url):
        thread = Thread(target=self.download, args=(url,))
        thread.start()

class LocalPlayer(object):
    def __init__(self):
        self.lock = Lock()
        self.playing = False
        self.queue = []

    def add(self, url):
        filename = Getter().get(url)
        
        with self.lock:
            self.queue.append(filename)
            if not self.playing:
                self._play(self.queue.pop(0), self._play_finished)

    def _play(self, filename, cb_complete):
        self.playing = True

        def run_thread(filename, cb_complete):
            print('==> Playing', filename)
            run(['ffplay', '-v', '0', '-nostats', '-hide_banner', '-autoexit', '-nodisp', filename])
            print('==> Playback complete')
            cb_complete()

        thread = Thread(target=run_thread, args=(filename, cb_complete))
        thread.start()

    def _play_finished(self):
        with self.lock:
            self.playing = False
            if len(self.queue) > 0:
                self._play(self.queue.pop(0), self._play_finished)

class Getter(object):
    def _progress_hook(self, progress):
        if progress['status'] == 'finished':
            self.filename = progress['filename']

    def get(self, url):
        options = {
            'format': 'mp3/mp4',
            'nocheckcertificate': 'FEDIPLAY_NO_CHECK_CERTIFICATE' in environ,
            'progress_hooks': [self._progress_hook]
        }
        with YoutubeDL(options) as downloader:
            downloader.download([url])

        return self.filename

class StreamListener(mastodon.StreamListener):
    players = {
            "local": LocalPlayer,
            "radio": RadioPlayer
            }

    def __init__(self, settings):
        self.tags = settings.setdefault("tags", ["fediplay"])
        p = settings.setdefault("player", "local")
        ps = settings.setdefault("player_settings", {})
        if p in self.players:
            self.player = self.players[p](ps)
        else:
            print("Unknown player: {}".format(p))

    def on_update(self, status):
        tags = extract_tags(status)
        for tag in tags:
            if tag in self.tags:
                links = extract_links(status)
                print("Added {}".format(links[0]))
                self.player.add(links[0])
                break

def register(api_base_url):
    old_umask = umask(0o77)
    Mastodon.create_app('fediplay', api_base_url=api_base_url, to_file='clientcred.secret')
    umask(old_umask)

def login(api_base_url, email, password):
    client = Mastodon(client_id='clientcred.secret', api_base_url=api_base_url)
    old_umask = umask(0o77)
    client.log_in(email, password, to_file='usercred.secret')
    umask(old_umask)

def stream(api_base_url, settings):
    client = Mastodon(client_id='clientcred.secret', access_token='usercred.secret', api_base_url=api_base_url)
    try: 
        mkdir("./music") 
    except: 
        pass
    listener = StreamListener(settings)
    print('==> Streaming from', api_base_url)
    client.user_stream(listener)

def extract_tags(toot):
    return [tag['name'] for tag in toot['tags']]

def has_external_link_class(class_string):
    classes = class_string.split(' ')
    if classes:
        return 'mention' in classes

    return False

def extract_links(toot):
    html = HTML(toot['content'])
    all_links = html.cssselect('a')
    return [link.attrib['href'] for link in all_links if not has_external_link_class(link.attrib.get('class', ''))]

def main():
    from getpass import getpass
    from os import path
    from sys import exit
    import json

    settings = {}
    with open("settings.json") as fp:
        settings = json.load(fp)

    api_base_url = settings["api_base_url"]
    if api_base_url == None:
        api_base_url = environ.get('FEDIPLAY_API_BASE_URL')
    if not api_base_url:
        print('api_base_url is not in settings nor is the FEDIPLAY_API_BASE_URL environment variable not set')
        exit(1)

    if not path.exists('clientcred.secret'):
        print('==> No clientcred.secret; registering application')
        register(api_base_url)

    if not path.exists('usercred.secret'):
        print('==> No usercred.secret; logging in')
        email = input('Email: ')
        password = getpass('Password: ')
        login(api_base_url, email, password)

    stream(api_base_url, settings)

if __name__ == '__main__':
    main()
