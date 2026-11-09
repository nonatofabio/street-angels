#!/usr/bin/env python3
"""Static site generator for the Santa Rosa Street Angels site.

Content lives in content/ (Markdown + YAML + JSON), templates in templates/,
and the finished site is written to build/.  Run:  python3 build.py
Set SITE_BASE=/street-angels/ when hosting under a sub-path (GitHub Pages).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
OUT = ROOT / "build"
BASE = os.environ.get("SITE_BASE", "/")
if not BASE.endswith("/"):
    BASE += "/"
TZ = ZoneInfo("America/Los_Angeles")
TODAY = dt.date.today()
HORIZON_DAYS = 75

env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)


# ---------- helpers ----------
def front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


IMG_RE = re.compile(r'<p><img alt="([^"]*)" src="([^"]+)"(?: title="([^"]*)")?\s*/?></p>')


def render_md(text: str) -> str:
    html = markdown.markdown(text, extensions=["smarty"])

    def fig(m):
        alt, src, title = m.group(1), m.group(2), m.group(3)
        if not src.startswith(("http", "/")):
            src = f"{BASE}assets/img/l/{src}"
        cap = f"<figcaption>{title}</figcaption>" if title else ""
        return f'<figure><img src="{src}" alt="{alt}" loading="lazy">{cap}</figure>'

    return IMG_RE.sub(fig, html)


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def write(path: str, html: str) -> None:
    p = OUT / path.strip("/")
    if not path.endswith(".ics"):
        p = p / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")


# ---------- content ----------
def load_cars() -> list[dict]:
    cars = []
    for f in sorted((CONTENT / "cars").glob("*.md")):
        fm, body = front_matter(f.read_text(encoding="utf-8"))
        year = str(fm.get("year") or "")
        decade = f"{year[:3]}0s" if len(year) == 4 else ""
        cars.append(
            {
                **fm,
                "slug": f.stem,
                "body_html": render_md(body),
                "body_text": body.strip(),
                "decade": decade,
                "year": year,
                "owner_slug": slugify(fm["owner"]),
            }
        )
    cars.sort(key=lambda c: c.get("order", 0))
    return cars


def nth_weekday(year: int, month: int, n: int, weekday: int) -> dt.date:
    d = dt.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + dt.timedelta(days=offset + 7 * (n - 1))


WD = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def occurrences(rule: str, start: dt.date, days: int) -> list[dt.date]:
    end = start + dt.timedelta(days=days)
    out = []
    kind, *rest = rule.split(":")
    if kind == "weekly":
        wd = WD[rest[0]]
        d = start + dt.timedelta(days=(wd - start.weekday()) % 7)
        while d <= end:
            out.append(d)
            d += dt.timedelta(days=7)
    elif kind == "monthly":
        n, wd = int(rest[0]), WD[rest[1]]
        y, m = start.year, start.month
        for _ in range(4):
            d = nth_weekday(y, m, n, wd)
            if start <= d <= end:
                out.append(d)
            m += 1
            if m > 12:
                m, y = 1, y + 1
    return out


def fmt_time(t: str) -> str:
    h, m = map(int, t.split(":"))
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"


def ics(ev: dict, occ: dict) -> str:
    def stamp(d: dt.datetime) -> str:
        return d.strftime("%Y%m%dT%H%M%S")

    desc = ev["blurb"].replace("\n", "\\n")
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Santa Rosa Street Angels//Events//EN",
            "BEGIN:VEVENT",
            f"UID:{ev['slug']}-{occ['date'].isoformat()}@santarosastreetangels",
            f"DTSTAMP:{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;TZID=America/Los_Angeles:{stamp(occ['start'])}",
            f"DTEND;TZID=America/Los_Angeles:{stamp(occ['end'])}",
            f"SUMMARY:{ev['title']}",
            f"LOCATION:{ev['location']}{', ' + ev['address'] if ev['address'] else ''}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def load_events() -> tuple[list[dict], list[dict]]:
    events = yaml.safe_load((CONTENT / "events.yaml").read_text(encoding="utf-8"))
    upcoming = []
    for ev in events:
        ev["start_fmt"] = fmt_time(ev["start"])
        ev["end_fmt"] = fmt_time(ev["end"])
        ev["directions"] = (
            "https://www.google.com/maps/dir/?api=1&destination="
            + urllib.parse.quote(ev["address"] or ev["location"])
        )
        ev["apple_maps"] = "https://maps.apple.com/?daddr=" + urllib.parse.quote(ev["address"] or ev["location"])
        ev["occurrences"] = []
        for d in occurrences(ev["rule"], TODAY, HORIZON_DAYS):
            sh, sm = map(int, ev["start"].split(":"))
            eh, em = map(int, ev["end"].split(":"))
            occ = {
                "date": d,
                "start": dt.datetime(d.year, d.month, d.day, sh, sm, tzinfo=TZ),
                "end": dt.datetime(d.year, d.month, d.day, eh, em, tzinfo=TZ),
                "event": ev,
            }
            occ["label"] = d.strftime("%A, %B %-d")
            occ["short"] = d.strftime("%a %b %-d")
            occ["ics_path"] = f"events/{ev['slug']}/{d.isoformat()}.ics"
            occ["gcal"] = (
                "https://calendar.google.com/calendar/render?action=TEMPLATE&"
                + urllib.parse.urlencode(
                    {
                        "text": ev["title"],
                        "dates": f"{occ['start'].strftime('%Y%m%dT%H%M%S')}/{occ['end'].strftime('%Y%m%dT%H%M%S')}",
                        "ctz": "America/Los_Angeles",
                        "location": f"{ev['location']}, {ev['address']}" if ev["address"] else ev["location"],
                        "details": ev["blurb"],
                    }
                )
            )
            ev["occurrences"].append(occ)
            upcoming.append(occ)
        ev["next"] = ev["occurrences"][0] if ev["occurrences"] else None
    upcoming.sort(key=lambda o: o["start"])
    return events, upcoming


def load_albums() -> list[dict]:
    albums = json.loads((CONTENT / "flickr.json").read_text(encoding="utf-8"))
    for a in albums:
        a["thumbs"] = [p + "_w.jpg" for p in a.get("photos", [])[:4]]
        a["cover"] = a["thumbs"][0] if a["thumbs"] else ""
        a["club"] = "street angels" in a["title"].lower() or "carr" in a["title"].lower() or "hot rodders" in a["title"].lower()
        if a.get("date"):
            a["date_fmt"] = dt.date.fromisoformat(a["date"]).strftime("%b %-d, %Y")
        else:
            a["date_fmt"] = ""
    return albums


# ---------- build ----------
def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets")
    shutil.copytree(ROOT / "static", OUT / "static")

    site = yaml.safe_load((CONTENT / "site.yaml").read_text(encoding="utf-8"))
    cars = load_cars()
    events, upcoming = load_events()
    albums = load_albums()

    owners: dict[str, list[dict]] = {}
    for c in cars:
        owners.setdefault(c["owner"], []).append(c)
    decades = sorted({c["decade"] for c in cars if c["decade"]})

    ctx = dict(site=site, base=BASE, year=TODAY.year, events=events, nav=[
        ("events/", "Events"), ("cars/", "Member's Cars"), ("photos/", "Photos"),
        ("history/", "History"), ("awards/", "Awards"), ("join/", "Join"),
    ])

    def page(path: str, template: str, **kw):
        write(path, env.get_template(template).render(**ctx, **kw))

    featured = [c for c in cars if c["title"] and c["image"]][::9][:6]
    next_each = sorted([ev["next"] for ev in events if ev["next"]], key=lambda o: o["start"])
    page("", "home.html", title=None, upcoming=next_each, albums=[a for a in albums if a["club"]][:3],
         featured=featured, car_count=len(cars), owner_count=len(owners))
    page("cars/", "cars.html", title="Member's Cars", cars=cars, owners=sorted(owners), decades=decades)
    for c in cars:
        others = [o for o in owners[c["owner"]] if o["slug"] != c["slug"]]
        page(f"cars/{c['slug']}/", "car.html", title=f"{c['title'] or c['owner']}", car=c, others=others)
    page("events/", "events.html", title="Events", upcoming=upcoming)
    for ev in events:
        if ev["next"]:
            page(f"events/{ev['slug']}/flyer/", "flyer.html", title=ev["title"], ev=ev, occ=ev["next"])
        for occ in ev["occurrences"]:
            write(occ["ics_path"], ics(ev, occ))
    page("photos/", "photos.html", title="Photos", albums=albums)
    for name in ("history", "awards", "join"):
        fm, body = front_matter((CONTENT / "pages" / f"{name}.md").read_text(encoding="utf-8"))
        page(f"{name}/", "page.html", title=fm["title"], subtitle=fm.get("subtitle", ""), body=render_md(body))

    # search index for the cars page (owner, title, text)
    idx = [{"slug": c["slug"], "owner": c["owner"], "title": c["title"], "year": c["year"], "decade": c["decade"], "text": c["body_text"][:300]} for c in cars]
    (OUT / "cars" / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    print(f"built {len(cars)} cars, {len(upcoming)} event dates, {len(albums)} albums -> {OUT}")


if __name__ == "__main__":
    main()
