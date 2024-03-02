import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import datetime as dt
import json
import smtplib
from stats_gen import *
from dotenv import load_dotenv

load_dotenv()

def str_to_datetime(str_dt: str):
    timestamp = str_dt.split('T')
    date = timestamp[0]
    time = timestamp[1]
    date_parts = date.split("-")
    time_parts = time.split(":")
    year = int(date_parts[0])
    month = int(date_parts[1])
    day = int(date_parts[2])
    hour = int(time_parts[0])
    min = int(time_parts[1])
    sec = int(time_parts[2][0:2])
    date_time = dt.datetime(year, month, day, hour, min, sec)
    return date_time


sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        scope=["user-read-recently-played", "playlist-modify-private"],
        redirect_uri="http://localhost:8000/music/callback/",
        client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
        client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
        show_dialog=True,
        cache_path="token.txt"
    )
)


user_id = sp.current_user()["id"]
recently_played = sp.current_user_recently_played(limit=50)['items']

song_names = []
artists = []
albums = []
times = []
durations_ms = []
track_ids = []
for track in recently_played:
    song = track['track']['name']
    artist = track['track']['artists'][0]['name']
    album = track['track']['album']['name']
    played_at = track['played_at']
    duration = track['track']['duration_ms']
    id = track['track']['id']
    song_names.append(song)
    artists.append(artist)
    albums.append(album)
    played_at_dt = str_to_datetime(played_at)
    times.append(played_at_dt)
    durations_ms.append(duration)
    track_ids.append(id)
song_names.reverse()
artists.reverse()
albums.reverse()
times.reverse()
durations_ms.reverse()
track_ids.reverse()

if os.path.exists("songs_played.json"):
    with open("songs_played.json", "r") as data:
        previously_played_data = json.load(data)
    prev_song_names = previously_played_data['song_names']
    prev_artists = previously_played_data['artists']
    prev_albums = previously_played_data['albums']
    prev_times = previously_played_data['time_played']
    prev_durations_ms = previously_played_data['duration_ms']
    prev_track_ids = previously_played_data['track_ids']
    time_lp_str = prev_times[-1]
    time_lp_dt_obj = dt.datetime.strptime(time_lp_str,
                                          '%d/%m/%y %H:%M:%S')

    i = 0
    times_len = len(times)
    while i < times_len:
        if times[i] <= time_lp_dt_obj:
            i += 1
            continue
        else:
            prev_song_names.append(song_names[i])
            prev_albums.append(albums[i])
            prev_artists.append(artists[i])
            prev_times.append(times[i].strftime('%d/%m/%y %H:%M:%S'))
            prev_durations_ms.append(durations_ms[i])
            prev_track_ids.append(track_ids[i])
            i += 1
    songs_data_dict = {
        'song_names': prev_song_names,
        'artists': prev_artists,
        'albums': prev_albums,
        'time_played': prev_times,
        'duration_ms': prev_durations_ms,
        'track_ids': prev_track_ids
    }

else:
    times_str = [dt_obj.strftime('%d/%m/%y %H:%M:%S') for dt_obj in times]

    songs_data_dict = {
        'song_names': song_names,
        'artists': artists,
        'albums': albums,
        'time_played': times_str,
        'duration_ms': durations_ms,
        'track_ids': track_ids
    }

with open('songs_played.json', 'w') as songs_played_file:
     json.dump(songs_data_dict, songs_played_file)

today = dt.datetime.today()
yesterday = today - dt.timedelta(1)
week_ago = today - dt.timedelta(7)
time_now = dt.datetime.now().time()

if today.weekday() == 5 and dt.time(0, 0) <= time_now <= dt.time(0, 14):
    weekly_tracks = create_track_list(songs_data_dict)
    playlist = sp.user_playlist_create(user=user_id,
                                       name=f"{week_ago.strftime('%d/%m/%y')} - {yesterday.strftime('%d/%m/%y')}",
                                       public=False)
    playlist_url = playlist['external_urls']['spotify']
    track_ids = []
    for track in weekly_tracks:
        if track[3] not in track_ids:
            track_ids.append(track[3])
    if len(track_ids) >= 100:
        while len(track_ids) >= 100:
            sp.playlist_add_items(playlist_id=playlist['id'], items=track_ids[0:100])
            del track_ids[0:100]
    sp.playlist_add_items(playlist_id=playlist['id'], items=track_ids)
    num_songs_played = len(weekly_tracks)
    calc_most_freq_song_result = calc_most_freq_played_song(weekly_tracks)
    most_freq_played_song = calc_most_freq_song_result[0]
    max_freq = calc_most_freq_song_result[1]
    most_freq_played_album = calc_most_freq_played_album(weekly_tracks)
    most_freq_played_artist = calc_most_freq_played_artist(weekly_tracks)
    total_time_played = 0
    for duration in songs_data_dict['duration_ms']:
        total_time_played += duration
    total_time_played_mins = round(total_time_played / 60000)
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(os.environ.get('FROM_EMAIL'), os.environ.get('FROM_PASSWORD'))
        connection.sendmail(
            from_addr=os.environ.get('FROM_EMAIL'),
            to_addrs=os.environ.get('TO_EMAIL'),
            msg=f"Subject:Your Weekly Spotify Stats\n\n With {max_freq} listens, {most_freq_played_song[0]} by {most_freq_played_song[2]} was your top song this week"
                f"\n{most_freq_played_album[1]}'s {most_freq_played_album[0]} was your favorite album this week"
                f"\nYour favorite artist this week was {most_freq_played_artist}\nYou listened to {total_time_played_mins}"
                f" minutes of music on Spotify this week spread over {num_songs_played} songs\n"
                f"Check Out Your Weekly Playlist: {playlist_url}"
        )
    os.remove('songs_played.json')