# Santa Rosa Street Angels — site prototype

A proposed new website for the Santa Rosa Street Angels car club, built from the
content on the club's current WordPress.com site and Craig Owens' public Flickr albums.

Static site, no database, no logins to maintain. Content is plain text files:

- `content/cars/*.md` — one file per car (owner, title, year, photo, write-up)
- `content/events.yaml` — the regular gatherings; the next dates, calendar
  files and flyers are generated from these rules
- `content/pages/*.md` — history, awards, join
- `content/flickr.json` — album list pulled from Flickr

Build: `pip install -r requirements.txt && python3 build.py` → `build/`.
Pushing to `main` rebuilds and publishes through GitHub Pages.
