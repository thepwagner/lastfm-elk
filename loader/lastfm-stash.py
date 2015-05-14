#!/usr/bin/env python

import os
import logging
import datetime
import time
import math
import socket
import json

import requests
import pytz


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('lastfm-stash')

LASTFM_URL = 'http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks'
# Obfusc-izzle from b-izz-ots.
LASTFM_KIZZEY = 'fcd63014e5b18c6c074dc2ee9ae411c3'

tz = pytz.timezone('UTC')

# lazy single threaded throttling
last_request = None

# Lazy wait for docker-compose to catch up
time.sleep(10)

logstash_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
logstash_socket.connect(('logstash', 5000))

def do_get(url):
    global last_request
    now = datetime.datetime.utcnow()
    if not last_request:
        resp = requests.get(url)
    else:
        time_since = now - last_request
        sleep_time = 10.0 - (time_since.microseconds / 1000000.0)
        if sleep_time > 0:
            logger.debug("Sleeping for %s", sleep_time)
            time.sleep(sleep_time)
        resp = requests.get(url)
    last_request = now
    return resp


def load_user_size(users):
    users_size = {}
    for user in users:
        logger.debug("Looking up %s" % user)
        user_url = '%s&user=%s&api_key=%s&format=json&limit=1' % (LASTFM_URL, user, LASTFM_KIZZEY)
        user_data = do_get(user_url)
        users_size[user] = int(user_data.json()['recenttracks']['@attr']['totalPages'])
    return users_size


def load_backlog(user_counts):
    for user, count in user_counts.items():
        user_pages = math.ceil(count / 200.0)

        for page in range(1, user_pages + 1):
            page_url = '%s&user=%s&api_key=%s&format=json&limit=200&page=%s' % (LASTFM_URL, user, LASTFM_KIZZEY, page)
            page_data = do_get(page_url)
            page_tracks = page_data.json()['recenttracks']['track']
            for track in page_tracks:
                if '@attr' in track \
                        and 'nowplaying' in track['@attr']:
                    continue

                track_event = {
                    'user': user
                }

                play_time = int(track['date']['uts'])
                play_time = datetime.datetime.fromtimestamp(play_time, tz=tz)
                track_event['@timestamp'] = play_time.isoformat()

                track_event['album'] = track['album']['#text']
                track_event['album_mb'] = track['album']['mbid']

                track_event['artist'] = track['artist']['#text']
                track_event['artist_mb'] = track['artist']['mbid']

                track_event['title'] = track['name']
                track_event['title_mb'] = track['mbid']

                track_json = json.dumps(track_event) + '\n'
                logstash_socket.send(bytes(track_json, 'utf-8'))


if __name__ == '__main__':
    if 'LASTFM_USERS' in os.environ:
        users = os.environ['LASTFM_USERS'].split(',')
    else:
        users = ['pwagner123']
    user_counts = load_user_size(users)
    print(user_counts)
    load_backlog(user_counts)
    # TODO: the plan was to slow polling (i.e. per 10 min) and add data in real time
