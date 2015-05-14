FROM python:3

ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD lastfm-stash.py /lastfm-stash.py
CMD /lastfm-stash.py
