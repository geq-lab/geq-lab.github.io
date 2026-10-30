#!/usr/bin/env python3
"""Build the Geodynamics & Earthquake Lab website.

Reads content/ and static/, renders templates/ and writes _site/, including
one page per person at /people/<slug>/ (templates/person.html).
SCHEMA.md describes the data files; HOWTO.md covers everyday edits.

    python build.py
    python build.py --content DIR --static DIR --templates DIR --out DIR

The build stops with a non-zero exit code and a message naming the file
when a YAML or BibTeX file does not parse, a required field is missing,
a people slug is not in people.yml, a figure has no credit, or a
site-relative link points at a page or anchor that does not exist.
"""

import argparse
import datetime as dt
import io
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import bibtexparser
import markdown
import yaml
from bibtexparser.middlewares import (LatexDecodingMiddleware,
                                      SeparateCoAuthors, SplitNameParts)
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent

ROLES = ["Principal Investigator", "Postdoctoral fellow", "Research staff",
         "PhD student", "MTech student", "BS-MS student", "Visiting scholar", "Intern"]
ROLE_RANK = {r: i for i, r in enumerate(ROLES)}
# The role inside a sentence ("Omkar, PhD student in the ..."), for the person pages' meta description.
ROLE_PHRASE = {"Principal Investigator": "principal investigator", "Postdoctoral fellow": "postdoctoral fellow",
               "Research staff": "research staff", "PhD student": "PhD student",
               "MTech student": "MTech student", "BS-MS student": "BS-MS student", "Visiting scholar": "visiting scholar", "Intern": "intern"}
GROUPS = ["current", "visiting", "alumni"]
LINK_KEYS = ["scholar", "orcid", "github", "website", "linkedin"]
LINK_LABELS = {"scholar": "Google Scholar", "orcid": "ORCID", "github": "GitHub",
               "website": "Website", "linkedin": "LinkedIn"}
PROJECT_STATUS = ["ongoing", "completed"]
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_LOOKUP = {m.lower(): i + 1 for i, m in enumerate(MONTHS)}
MONTH_LOOKUP.update({
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7,
    "august": 8, "september": 9, "sept": 9, "october": 10, "november": 11,
    "december": 12})

PHOTO_SIZE = 480
PHOTO_QUALITY = 85
FIGURE_MAX = 1600
# A PNG under static/ that is still bigger than this after resizing is written with a
# 256-colour palette, which cuts a photographic composite from about 1 MB to 300 KB.
PNG_MAX_BYTES = 300_000
LOGO_SIZES = {"logo.png": 1080, "logo-240.png": 240}
FAVICON_SIZE = 64
# Square window around the globe in static/logo.png (1080x1080); used for the favicon.
LOGO_GLOBE_BOX = (40, 150, 580, 690)
# Files under static/ that stay in the repository but are not published.
STATIC_SKIP = {"logo_green.png"}

# Category order within a year on the Publications page.
CATEGORIES = ["journal", "chapter", "conference", "thesis", "dataset",
              "preprint", "other", "abstract"]
CATEGORY_LABEL = {
    "journal": "Journal papers", "chapter": "Book chapters",
    "conference": "Conference papers", "thesis": "Theses",
    "dataset": "Datasets", "preprint": "Preprints", "other": "Other",
    "abstract": "Conference abstracts"}

# Short form of the institute for the person pages' meta description
# ("Omkar, PhD student in the Geodynamics & Earthquake Lab, IIT Gandhinagar.").
INSTITUTE_SHORT = "IIT Gandhinagar"
# Longest meta description written for a person page; search results cut at about 160 characters.
DESCRIPTION_MAX = 160

# The nine pages in the navigation, in order. The home page is the logo link.
PAGES = [
    ("research", "Research"), ("people", "People"),
    ("publications", "Publications"), ("news", "News"),
    ("awards", "Awards"), ("teaching", "Teaching"),
    ("projects", "Projects"), ("join", "Join us"), ("contact", "Contact"),
]

ID_RE = re.compile(r'\bid="([^"]+)"')


class BuildError(Exception):
    """A problem in the content that the editor has to fix."""


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------

def md(text):
    """Render Markdown to HTML. Links open in the same tab; no raw HTML needed."""
    if not text:
        return Markup("")
    return Markup(markdown.markdown(str(text), extensions=["extra", "sane_lists"]))


def fmt_date(d):
    """2026-06-12 -> '12 Jun 2026'."""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def parse_month(value):
    """BibTeX month field -> 1..12 or None."""
    if value is None:
        return None
    s = str(value).strip().strip("{}").lower().rstrip(".")
    if s.isdigit() and 1 <= int(s) <= 12:
        return int(s)
    return MONTH_LOOKUP.get(s[:3]) if s[:3] in MONTH_LOOKUP else MONTH_LOOKUP.get(s)


def parse_when(value):
    """'2021', 2021 or 'Jul 2023' -> (year, month) for sorting; month 0 if unknown."""
    if value is None or value == "":
        return None
    s = str(value).strip()
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return (int(m.group(1)), 0)
    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{4})", s)
    if m and m.group(1).lower()[:3] in MONTH_LOOKUP:
        return (int(m.group(2)), MONTH_LOOKUP[m.group(1).lower()[:3]])
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(-\d{1,2})?", s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def year_of(value):
    w = parse_when(value)
    return w[0] if w else None


def truthy(value):
    return str(value).strip().strip("{}").lower() in ("true", "yes", "1")


def norm_name(s):
    """Lower-case ASCII letters only, for matching names across spellings of accents."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def initials(name):
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


def load_yaml(path, expect):
    """Parse a YAML file and check it is a list or a mapping as expected."""
    if not path.exists():
        raise BuildError(f"{path}: file is missing")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as e:
        where = ""
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            where = f" (line {mark.line + 1}, column {mark.column + 1})"
        raise BuildError(f"{path}{where}: YAML does not parse. {e}")
    if data is None:
        data = [] if expect is list else {}
    if not isinstance(data, expect):
        kind = "a list" if expect is list else "a mapping"
        raise BuildError(f"{path}: expected {kind} at the top level")
    return data


def need(record, key, where):
    value = record.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise BuildError(f"{where}: required field '{key}' is missing")
    return value


def as_list(value, where, key):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    raise BuildError(f"{where}: '{key}' must be a list")


# ----------------------------------------------------------------------------
# Content loaders
# ----------------------------------------------------------------------------

def load_site(content, static):
    path = content / "site.yml"
    site = load_yaml(path, dict)
    where = str(path)
    for key in ("name", "url", "description", "pi"):
        need(site, key, where)
    site.setdefault("short_name", site["name"])
    site.setdefault("institute", "")
    site.setdefault("department", "")
    site["url"] = site["url"].rstrip("/") + "/"
    contact = site.get("contact") or {}
    need(contact, "email", f"{where} contact")
    contact.setdefault("phone", "")
    contact["address"] = as_list(contact.get("address"), where, "contact.address")
    contact.setdefault("map_url", "")
    site["contact"] = contact
    links = site.get("links") or []
    for i, link in enumerate(links):
        if not isinstance(link, dict) or not link.get("label") or not link.get("url"):
            raise BuildError(f"{where}: links[{i}] needs 'label' and 'url'")
    site["links"] = links
    home = site.get("home") or {}
    need(home, "intro", f"{where} home")
    for key in ("news_count", "pubs_count"):
        try:
            home[key] = int(home.get(key, 5))
        except (TypeError, ValueError):
            raise BuildError(f"{where} home: {key} must be a whole number, got '{home.get(key)}'")
    home["figures"] = load_figures(home.get("figures"), static, f"{where} home", "figures")
    n_fig = len(home["figures"])
    if home["figures"] and not 4 <= n_fig <= 8:
        warn(f"{where} home: {n_fig} figures on the home page; SCHEMA.md suggests 4 to 8")
    site["home"] = home
    site.setdefault("contact_text", "")
    site.setdefault("footer_note", "")
    site["page_intros"] = site.get("page_intros") or {}
    facilities = site.get("facilities") or []
    for i, f in enumerate(facilities):
        if not isinstance(f, dict) or not f.get("name"):
            raise BuildError(f"{where}: facilities[{i}] needs a 'name'")
        f.setdefault("note", "")
    site["facilities"] = facilities
    return site


def load_people(content):
    path = content / "people.yml"
    raw = load_yaml(path, list)
    # A block without the leading "- " merges silently into the previous person
    # (the later slug wins), so count the slug lines against the parsed entries.
    n_slug_lines = len(re.findall(r"^\s*-?\s*slug:", path.read_text(encoding="utf-8-sig"), re.M))
    if n_slug_lines != len(raw):
        raise BuildError(f"{path}: {n_slug_lines} 'slug:' lines but {len(raw)} entries; "
                         f"every person must start with '- slug:' (note the dash)")
    people = []
    seen = set()
    for i, rec in enumerate(raw):
        where = f"{path} entry {i + 1}"
        if not isinstance(rec, dict):
            raise BuildError(f"{where}: each entry must be a mapping (start it with '- slug:')")
        slug = str(need(rec, "slug", where)).strip()
        where = f"{path} '{slug}'"
        if not SLUG_RE.match(slug):
            raise BuildError(f"{where}: slug must be lower-case letters, digits and hyphens")
        if slug in seen:
            raise BuildError(f"{where}: duplicate slug")
        seen.add(slug)
        role = str(need(rec, "role", where)).strip()
        if role not in ROLES:
            raise BuildError(f"{where}: role '{role}' is not one of: {', '.join(ROLES)}")
        group = str(rec.get("group") or "current").strip()
        if group not in GROUPS:
            raise BuildError(f"{where}: group '{group}' is not one of: {', '.join(GROUPS)}")
        links = rec.get("links") or {}
        if not isinstance(links, dict):
            raise BuildError(f"{where}: links must be a mapping like {{scholar: URL, github: URL}}")
        for k in links:
            if k not in LINK_KEYS:
                warn(f"{where}: unknown link key '{k}' (known: {', '.join(LINK_KEYS)})")
        email = str(rec.get("email") or "").strip()
        if email and re.search(r"@(gmail|yahoo|hotmail|outlook|rediffmail)\.", email, re.I):
            warn(f"{where}: '{email}' is not an institutional address; SCHEMA.md allows only those")
        # `about` is the Markdown text of the person's own page. It lives inside the
        # person's own entry, so an about without a matching slug cannot happen; what
        # can happen is a wrongly indented block that YAML reads as a mapping or a list.
        about = rec.get("about")
        if about is not None and not isinstance(about, str):
            raise BuildError(f"{where}: 'about' must be a block of text (write it as 'about: |' and indent "
                             f"the lines under it), but YAML read it as {type(about).__name__}")
        about = (about or "").strip()
        n_words = len(about.split())
        if about and n_words > 300:
            warn(f"{where}: 'about' has {n_words} words; SCHEMA.md suggests 100 to 250")
        # Every current and visiting member and every past member other than an intern
        # gets a page at /people/<slug>/; a past intern gets one only with an `about`.
        has_page = bool(about) or group != "alumni" or role != "Intern"
        person = {
            "slug": slug,
            "name": str(need(rec, "name", where)).strip(),
            "role": role,
            "group": group,
            "title_line": str(rec.get("title_line") or "").strip(),
            "since": "" if rec.get("since") is None else str(rec.get("since")).strip(),
            "until": "" if rec.get("until") is None else str(rec.get("until")).strip(),
            "degree": str(rec.get("degree") or "").strip(),
            "now": str(rec.get("now") or "").strip(),
            "topic": str(rec.get("topic") or "").strip(),
            "email": email,
            "cosupervisor": str(rec.get("cosupervisor") or "").strip(),
            "links": [(k, LINK_LABELS[k], str(links[k])) for k in LINK_KEYS if links.get(k)],
            "bio": md(rec.get("bio") or ""),
            "about": md(about),
            "affiliation_then": str(rec.get("affiliation_then") or "").strip(),
            "url": f"/people/{slug}/" if has_page else "",   # "" : no page, show the name as plain text
            "order": i,
            "photo": "",          # filled in by process_photos
            "initials": "",
            "papers": [],         # filled in by attach_person_items
            "abstracts": [],
            "news": [],
            "awards": [],
        }
        person["initials"] = initials(person["name"])
        if group == "alumni" and not person["until"]:
            warn(f"{where}: alumni entry without 'until'")
        if person["affiliation_then"] and group != "alumni":
            warn(f"{where}: 'affiliation_then' is for alumni only (SCHEMA.md) and is not shown for a "
                 f"current member; say where they started in 'title_line' instead")
        people.append(person)
    if not people:
        raise BuildError(f"{path}: no entries")
    return people


def person_sections(people):
    """Group and order people for the People page."""
    current = [p for p in people if p["group"] == "current"]

    def cur_key(p):
        when = parse_when(p["since"]) or (9999, 0)
        return (ROLE_RANK[p["role"]], when, p["order"])
    current.sort(key=cur_key)

    def pick(roles):
        return [p for p in current if p["role"] in roles]

    visiting = [p for p in people if p["group"] == "visiting"] + pick(["Visiting scholar"])
    visiting.sort(key=lambda p: (parse_when(p["since"]) or (9999, 0), p["order"]))

    alumni = [p for p in people if p["group"] == "alumni"]

    def alum_key(p):
        y = year_of(p["until"]) or year_of(p["since"]) or 0
        return (-y, ROLE_RANK[p["role"]], p["order"])
    alumni.sort(key=alum_key)
    past_interns = [p for p in alumni if p["role"] == "Intern"]
    alumni = [p for p in alumni if p["role"] != "Intern"]
    interns_by_year = []
    for p in past_interns:
        y = year_of(p["until"]) or year_of(p["since"]) or 0
        if interns_by_year and interns_by_year[-1][0] == y:
            interns_by_year[-1][1].append(p)
        else:
            interns_by_year.append((y, [p]))

    sections = [
        ("Faculty", "grid", pick(["Principal Investigator"])),
        ("Postdoctoral fellows and research staff", "grid",
         pick(["Postdoctoral fellow", "Research staff"])),
        ("PhD students", "grid", pick(["PhD student"])),
        ("MTech students", "grid", pick(["MTech student"])),
        ("Interns", "grid", pick(["Intern"])),
        ("Visiting scholars", "grid", visiting),
    ]
    return [s for s in sections if s[2]], alumni, interns_by_year


def attach_person_items(people, pubs, news, awards):
    """Fill each person's papers, abstracts, news and awards for their own page.
    Papers come from the author matching done in load_publications (surname plus
    first initial, exact for a mononym), news from the `people` lists and awards
    from `who`. Each list keeps the newest-first order of its source."""
    for p in people:
        slug = p["slug"]
        mine = [pub for pub in pubs if slug in pub["people"]]
        p["papers"] = [pub for pub in mine if pub["category"] != "abstract"]
        p["abstracts"] = [pub for pub in mine if pub["category"] == "abstract"]
        p["news"] = [n for n in news if any(q["slug"] == slug for q in n["people"])]
        p["awards"] = [a for a in awards if any(w["slug"] == slug for w in a["who"])]


def check_slugs(slugs, people_by_slug, where):
    for s in slugs:
        if not isinstance(s, str) or s not in people_by_slug:
            known = ", ".join(sorted(people_by_slug))
            raise BuildError(f"{where}: people slug '{s}' is not in people.yml (known slugs: {known})")


def figure_output_size(w, h):
    """Size of a figure under static/img/ after the build's resizing."""
    if max(w, h) <= FIGURE_MAX:
        return w, h
    scale = FIGURE_MAX / max(w, h)
    return round(w * scale), round(h * scale)


def figure_size(static, image, where):
    """(width, height) the published figure will have, for the img attributes."""
    path = static / image
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
    except (OSError, ValueError) as e:
        raise BuildError(f"{where}: cannot read image '{image}' ({e})")
    return figure_output_size(w, h) if image.startswith("img/") else (w, h)


def check_image(static, image, where):
    """An image reference is a path under static/, such as img/figure.png."""
    if image.startswith("/") or ".." in Path(image).parts or "\\" in image:
        raise BuildError(f"{where}: image '{image}' must be a path under static/, like img/figure.png")
    if image in STATIC_SKIP:
        raise BuildError(f"{where}: image '{image}' is not published (see STATIC_SKIP in build.py)")
    if not (static / image).is_file():
        raise BuildError(f"{where}: image '{image}' is not under static/")


def check_link(link, where, key="link"):
    """A link is site-relative (/research/#wedges), an anchor, or an http(s) URL."""
    if link and not (link.startswith("/") or link.startswith("#")
                     or re.match(r"https?://", link, re.I)):
        raise BuildError(f"{where}: {key} must start with /, # or http(s)://, got '{link[:40]}'")


FIGURE_KEYS = ("image", "alt", "caption", "credit", "link")


def load_figures(items, static, where, key):
    """A list of {image, alt, caption, credit, link?} (site.yml home.figures,
    research.yml images). image, alt, caption and credit are required; the
    figure links to `link` if given, otherwise to the full-size image."""
    items = as_list(items, where, key)
    figures = []
    for i, rec in enumerate(items):
        here = f"{where} {key}[{i + 1}]"
        if not isinstance(rec, dict):
            raise BuildError(f"{here}: each figure must be a mapping with image, alt, caption and credit "
                             f"(start it with '- image:')")
        for k in rec:
            if k not in FIGURE_KEYS:
                warn(f"{here}: unknown field '{k}' (known: {', '.join(FIGURE_KEYS)})")
        image = str(need(rec, "image", here)).strip()
        check_image(static, image, here)
        alt = str(need(rec, "alt", here)).strip()
        caption = str(need(rec, "caption", here)).strip()
        credit = str(need(rec, "credit", here)).strip()
        link = str(rec.get("link") or "").strip()
        check_link(link, here)
        w, h = figure_size(static, image, here)
        src = "/static/" + image
        figures.append({
            "image": image,
            "src": src,
            "alt": alt,
            "caption": caption,
            "credit": credit,
            "link": link,
            "href": link or src,
            "w": w,
            "h": h,
            "where": here,
        })
    return figures


def load_research(content, static, people_by_slug):
    path = content / "research.yml"
    raw = load_yaml(path, list)
    themes = []
    seen = set()
    for i, rec in enumerate(raw):
        where = f"{path} entry {i + 1}"
        if not isinstance(rec, dict):
            raise BuildError(f"{where}: each theme must be a mapping (start it with '- id:')")
        tid = str(need(rec, "id", where)).strip()
        where = f"{path} theme '{tid}'"
        if not SLUG_RE.match(tid):
            raise BuildError(f"{where}: id must be lower-case letters, digits and hyphens")
        if tid in seen:
            raise BuildError(f"{where}: duplicate id")
        seen.add(tid)
        image = str(rec.get("image") or "").strip()
        image_w = image_h = 0
        if image:
            check_image(static, image, where)
            if not rec.get("image_credit"):
                raise BuildError(f"{where}: image_credit is required when image is set")
            image_w, image_h = figure_size(static, image, where)
        slugs = as_list(rec.get("people"), where, "people")
        check_slugs(slugs, people_by_slug, where)
        themes.append({
            "id": tid,
            "title": str(need(rec, "title", where)).strip(),
            "summary": md(need(rec, "summary", where)),
            "image": image,
            "image_w": image_w,
            "image_h": image_h,
            "image_alt": str(rec.get("image_alt") or rec.get("title")).strip(),
            "image_caption": str(rec.get("image_caption") or "").strip(),
            "image_credit": str(rec.get("image_credit") or "").strip(),
            "images": load_figures(rec.get("images"), static, where, "images"),
            "people": [people_by_slug[s] for s in slugs],
            "papers": [],   # filled from publications.bib
        })
    return themes


def load_projects(content):
    path = content / "projects.yml"
    raw = load_yaml(path, list)
    projects = []
    for i, rec in enumerate(raw):
        where = f"{path} entry {i + 1}"
        if not isinstance(rec, dict):
            raise BuildError(f"{where}: each project must be a mapping (start it with '- title:')")
        status = str(need(rec, "status", where)).strip().lower()
        if status not in PROJECT_STATUS:
            raise BuildError(f"{where}: status '{status}' is not one of: {', '.join(PROJECT_STATUS)}")
        projects.append({
            "title": str(need(rec, "title", where)).strip(),
            "agency": str(need(rec, "agency", where)).strip(),
            "role": str(rec.get("role") or "").strip(),
            "years": str(rec.get("years") or "").strip(),
            "status": status,
            "note": str(rec.get("note") or "").strip(),
        })
    ongoing = [p for p in projects if p["status"] == "ongoing"]
    completed = [p for p in projects if p["status"] == "completed"]
    return ongoing, completed


def load_teaching(content):
    path = content / "teaching.yml"
    raw = load_yaml(path, list)
    courses = []
    for i, rec in enumerate(raw):
        where = f"{path} entry {i + 1}"
        if not isinstance(rec, dict):
            raise BuildError(f"{where}: each course must be a mapping (start it with '- code:')")
        courses.append({
            "code": str(need(rec, "code", where)).strip(),
            "title": str(need(rec, "title", where)).strip(),
            "level": str(rec.get("level") or "").strip(),
            "offered": [str(s) for s in as_list(rec.get("offered"), where, "offered")],
            "link": str(rec.get("link") or "").strip(),
            "note": str(rec.get("note") or "").strip(),
        })
    return courses


def load_awards(content, people_by_slug):
    """content/awards.yml (optional): a list of {year, date?, who, title, giver, for?, link?}.
    `who` holds people.yml slugs, which link to the People page, or plain names
    in quotes for someone outside the group. Newest first."""
    path = content / "awards.yml"
    if not path.exists():
        return []
    raw = load_yaml(path, list)
    awards = []
    for i, rec in enumerate(raw):
        where = f"{path} entry {i + 1}"
        if not isinstance(rec, dict):
            raise BuildError(f"{where}: each award must be a mapping (start it with '- year:')")
        year = str(need(rec, "year", where)).strip()
        if not re.fullmatch(r"\d{4}", year):
            raise BuildError(f"{where}: year must be four digits, got '{year}'")
        year = int(year)
        date = rec.get("date")
        if isinstance(date, dt.datetime):
            date = date.date()
        elif date is not None and not isinstance(date, dt.date):
            try:
                date = dt.date.fromisoformat(str(date).strip())
            except ValueError:
                raise BuildError(f"{where}: date must be YYYY-MM-DD, got '{date}'")
        if date and date.year != year:
            raise BuildError(f"{where}: date {date} is not in year {year}")
        who = []
        for w in as_list(rec.get("who"), where, "who"):
            w = str(w).strip()
            if w in people_by_slug:
                who.append({"name": people_by_slug[w]["name"], "slug": w,
                            "url": people_by_slug[w]["url"]})
            elif SLUG_RE.match(w):
                raise BuildError(f"{where}: who '{w}' looks like a slug but is not in people.yml")
            else:
                who.append({"name": w, "slug": "", "url": ""})   # someone outside the group, shown as text
        if not who:
            raise BuildError(f"{where}: 'who' must name at least one person")
        link = str(rec.get("link") or "").strip()
        check_link(link, where)
        awards.append({
            "year": year,
            "date": date,
            "date_text": fmt_date(date) if date else str(year),
            "who": who,
            "title": str(need(rec, "title", where)).strip(),
            "giver": str(need(rec, "giver", where)).strip(),
            "for": str(rec.get("for") or "").strip(),
            "link": link,
            "order": i,
            "where": where,
        })
    # Newest first: year, then date (undated entries after the dated ones of that year), then file order.
    awards.sort(key=lambda a: (-a["year"], -(a["date"].toordinal() if a["date"] else 0), a["order"]))
    return awards


def load_join(content):
    path = content / "join.md"
    if not path.exists():
        raise BuildError(f"{path}: file is missing")
    text = path.read_text(encoding="utf-8")
    title = "Join us"
    m = re.match(r"\s*#\s+(.+?)\s*\n", text)
    if m:
        title = m.group(1).strip()
        text = text[m.end():]
    return title, md(text)


def split_front_matter(path):
    text = path.read_text(encoding="utf-8-sig")   # -sig: a BOM from Notepad is dropped
    m = re.match(r"---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", text, re.S)
    if not m:
        raise BuildError(f"{path}: the file must start with a '---' front matter block, see SCHEMA.md")
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise BuildError(f"{path}: front matter does not parse as YAML. {e}")
    if not isinstance(meta, dict):
        raise BuildError(f"{path}: front matter must be 'key: value' lines")
    return meta, m.group(2)


def load_news(content, static, people_by_slug):
    folder = content / "news"
    items = []
    if not folder.is_dir():
        warn(f"{folder}: no news folder, the News page will be empty")
        return items
    for path in sorted(folder.glob("*.md")):
        where = str(path)
        if not re.match(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$", path.name):
            warn(f"{where}: file name should look like 2026-06-10-short-slug.md")
        meta, body = split_front_matter(path)
        title = str(need(meta, "title", where)).strip()
        date = need(meta, "date", where)
        if isinstance(date, dt.datetime):
            date = date.date()
        elif not isinstance(date, dt.date):
            try:
                date = dt.date.fromisoformat(str(date).strip())
            except ValueError:
                raise BuildError(f"{where}: date must be YYYY-MM-DD, got '{date}'")
        image = str(meta.get("image") or "").strip()
        image_w = image_h = 0
        image_caption = str(meta.get("image_caption") or "").strip()
        image_credit = str(meta.get("image_credit") or "").strip()
        if image:
            check_image(static, image, where)
            image_w, image_h = figure_size(static, image, where)
            if not image_credit:
                raise BuildError(f"{where}: image_credit is required when image is set; "
                                 f"every figure on the site is credited")
        elif image_caption or image_credit:
            warn(f"{where}: image_caption/image_credit given but no image, ignoring them")
            image_caption = image_credit = ""
        link = str(meta.get("link") or "").strip()
        check_link(link, where)
        slugs = as_list(meta.get("people"), where, "people")
        check_slugs(slugs, people_by_slug, where)
        items.append({
            "id": path.stem,
            "title": title,
            "date": date,
            "date_text": fmt_date(date),
            "link": link,
            "image": image,
            "image_src": "/static/" + image if image else "",
            "image_w": image_w,
            "image_h": image_h,
            "image_caption": image_caption,
            "image_credit": image_credit,
            "people": [people_by_slug[s] for s in slugs],
            "body": md(body.strip()),
            "file": path.name,
            "where": where,
        })
    items.sort(key=lambda n: (n["date"], n["file"]), reverse=True)
    return items


def group_by_year(items, key):
    groups = []
    for item in items:
        y = key(item)
        if groups and groups[-1][0] == y:
            groups[-1][1].append(item)
        else:
            groups.append((y, [item]))
    return groups


# ----------------------------------------------------------------------------
# Publications
# ----------------------------------------------------------------------------

class NameMatcher:
    """Decides whether a BibTeX author is someone in people.yml.

    Match on surname plus first initial. A person with a single-word name
    (a mononym) matches only a BibTeX author written as {Name} with no
    given name. Surnames are compared without accents or case, and a
    multi-word surname in people.yml matches on any split, so 'Devanarayanan
    E M' matches both 'E M, Devanarayanan' and 'M, Devanarayanan E'.
    """

    def __init__(self, people):
        self.keys = {}
        # (surname, initial) shared by two members (Aniket Kumar, Amarjeet Kumar) -> {normalised given name: slug}.
        # Such an author is matched on the full given name; one written with only the initial matches nobody.
        self.shared = {}
        self.warned = set()
        names = {p["slug"]: p["name"] for p in people}
        for p in people:
            words = [w for w in re.split(r"\s+", p["name"]) if w]
            if len(words) == 1:
                self.keys[(norm_name(words[0]), "")] = p["slug"]
                continue
            given = norm_name(words[0])
            for k in range(1, len(words)):
                key = (norm_name("".join(words[k:])), given[:1])
                other = self.keys.get(key)
                if other is None:
                    self.keys[key] = p["slug"]
                elif other != p["slug"]:
                    if key not in self.shared:
                        warn(f"people.yml: '{names[other]}' and '{p['name']}' share the surname and first initial; "
                             f"a BibTeX author written with only the initial will be matched to neither")
                        self.shared[key] = {norm_name(names[other].split()[0]): other}
                    self.shared[key][given] = p["slug"]

    def match(self, author):
        """author: NameParts from bibtexparser. Returns a slug or None."""
        first = " ".join(author.first).strip()
        last = norm_name("".join(author.last))
        if not first:
            return self.keys.get((last, ""))
        initial = norm_name(first)[:1]
        key = (last, initial)
        if key not in self.keys and author.von:
            key = (norm_name("".join(author.von) + "".join(author.last)), initial)
        if key in self.shared:
            given = norm_name(first.split()[0])
            if len(given) > 1:
                return self.shared[key].get(given)
            label = f"{first} {' '.join(author.last)}"
            if label not in self.warned:
                self.warned.add(label)
                warn(f"publications.bib: author '{label}' could be any of "
                     f"{', '.join(sorted(self.shared[key].values()))}; write the full given name to match")
            return None
        return self.keys.get(key)


def clean_text(value):
    """Tidy a decoded BibTeX string: braces gone, maths subscripts to HTML."""
    s = str(value).replace("{", "").replace("}", "").strip()
    s = re.sub(r"\s+", " ", s)
    s = str(escape(s))   # plain str: re.sub on a Markup would escape the tags below
    s = re.sub(r"\$_\\?\{?([^$}]+)\}?\$", r"<sub>\1</sub>", s)
    s = re.sub(r"\$\^\\?\{?([^$}]+)\}?\$", r"<sup>\1</sup>", s)
    return Markup(s)


def linkify(markup):
    """Turn bare http(s) URLs in already-escaped text into links (used for `note`)."""
    def repl(m):
        url = m.group(0)
        trail = ""
        while url and url[-1] in ".,;:)":
            trail = url[-1] + trail
            url = url[:-1]
        return f'<a href="{url}">{url}</a>{trail}'
    return Markup(re.sub(r"https?://[^\s<]+", repl, str(markup)))


def author_display(author):
    """NameParts -> 'U. Mannu', 'T. S. van der Voort', or 'Omkar'."""
    last = " ".join(author.last).replace("{", "").replace("}", "").strip()
    von = " ".join(author.von).strip()
    firsts = [w for w in author.first if w]
    if not firsts:
        return last
    inits = []
    for w in firsts:
        w = w.replace("{", "").replace("}", "")
        for part in re.split(r"[-]", w):
            if part:
                inits.append(part[0].upper() + ".")
    given = " ".join(inits)
    jr = " ".join(author.jr).strip()
    name = f"{given} {von + ' ' if von else ''}{last}"
    return f"{name}, {jr}" if jr else name


def join_authors(parts):
    if len(parts) <= 1:
        return Markup("").join(parts)
    return Markup(", ").join(parts[:-1]) + Markup(" and ") + parts[-1]


def doi_url(doi):
    doi = str(doi).strip()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    return doi, "https://doi.org/" + doi


def classify(entry_type, fields):
    t = entry_type.lower()
    if t == "article":
        return "journal"
    if t in ("incollection", "inbook"):
        return "chapter"
    if t == "inproceedings":
        return "abstract" if truthy(fields.get("abstract_only", "")) else "conference"
    if t in ("phdthesis", "mastersthesis"):
        return "thesis"
    if t == "misc":
        kind = str(fields.get("kind", "")).strip().lower()
        if kind in ("dataset", "preprint"):
            return kind
        return "other"
    return "other"


def venue_html(pub):
    """The part after the title: journal, volume, pages, and so on."""
    f = pub["fields"]
    t = pub["entry_type"]
    cat = pub["category"]
    status = f.get("status", "").strip()
    bits = []
    if cat == "journal":
        if f.get("journal"):
            bits.append(clean_text(f["journal"]))
        if status:
            bits.append(escape(status))
        else:
            vol = f.get("volume", "")
            num = f.get("number", "")
            if vol:
                bits.append(escape(f"{vol}({num})" if num else vol))
            if f.get("pages"):
                bits.append(escape(f["pages"]))
    elif cat == "chapter":
        if f.get("booktitle"):
            bits.append(Markup("In: ") + clean_text(f["booktitle"]))
        if f.get("publisher"):
            bits.append(clean_text(f["publisher"]))
        if status:
            bits.append(escape(status))
        elif f.get("pages"):
            bits.append(escape("pp. " + f["pages"]))
    elif cat in ("conference", "abstract"):
        if f.get("booktitle"):
            bits.append(clean_text(f["booktitle"]))
        if status:
            bits.append(escape(status))
        elif f.get("pages"):
            bits.append(escape("pp. " + f["pages"]))
    elif cat == "thesis":
        label = "PhD thesis" if t == "phdthesis" else "Master's thesis"
        bits.append(escape(label))
        if f.get("school"):
            bits.append(clean_text(f["school"]))
    elif cat == "dataset":
        bits.append(escape("Dataset"))
        if f.get("publisher"):
            bits.append(clean_text(f["publisher"]))
        if status:
            bits.append(escape(status))
    elif cat == "preprint":
        bits.append(escape("Preprint"))
        for key in ("publisher", "journal", "booktitle"):
            if f.get(key):
                bits.append(clean_text(f[key]))
                break
        if status:
            bits.append(escape(status))
    else:
        for key in ("journal", "booktitle", "publisher", "howpublished", "school"):
            if f.get(key):
                bits.append(clean_text(f[key]))
        if status:
            bits.append(escape(status))
    return Markup(", ").join(bits)


def cite_html(pub):
    """One citation: authors. <i>Title</i>. Venue (year). links."""
    out = pub["authors_html"] + Markup(". <i>") + pub["title"] + Markup("</i>. ")
    if pub["venue_html"]:
        out += pub["venue_html"] + Markup(" ")
    out += Markup(f"({pub['year']}).")
    if pub["doi"]:
        out += Markup(f' <a href="{escape(pub["doi_url"])}">doi:{escape(pub["doi"])}</a>')
    elif pub["url"]:
        out += Markup(f' <a href="{escape(pub["url"])}">Full text</a>')
    if pub["openaccess"]:
        out += Markup(' <span class="oa" title="Open access">open access</span>')
    if pub["note"]:
        out += Markup(' <span class="note">') + pub["note"] + Markup("</span>")
    return out


def load_publications(content, matcher, themes_by_id):
    path = content / "publications.bib"
    if not path.exists():
        raise BuildError(f"{path}: file is missing")
    try:
        lib = bibtexparser.parse_file(
            str(path),
            append_middleware=[LatexDecodingMiddleware(), SeparateCoAuthors(), SplitNameParts()])
    except Exception as e:  # the parser itself gave up
        raise BuildError(f"{path}: BibTeX does not parse. {e}")
    if lib.failed_blocks:
        lines = []
        for b in lib.failed_blocks:
            start = getattr(b, "start_line", None)
            where = f"line {start + 1}" if isinstance(start, int) else "unknown line"
            err = getattr(b, "error", None)
            reason = getattr(err, "abort_reason", None) or str(err or "").strip()
            lines.append(f"  {where}: {reason or 'could not parse this block'}")
        raise BuildError(f"{path}: BibTeX does not parse. Check the braces and the commas "
                         f"between fields.\n" + "\n".join(lines))

    pubs = []
    seen = set()
    for i, e in enumerate(lib.entries):
        where = f"{path} entry '{e.key}'"
        if e.key in seen:
            raise BuildError(f"{where}: duplicate citation key")
        seen.add(e.key)
        fields = {}
        for k, fv in e.fields_dict.items():
            fields[k.lower()] = fv.value
        authors = fields.get("author")
        if isinstance(authors, list):
            for a in authors:
                joined = " ".join(a.first + a.von + a.last + a.jr)
                if "=" in joined or "\n" in joined or len(joined) > 80:
                    raise BuildError(f"{where}: the author field looks wrong ('{joined[:60]}...'). "
                                     f"Is a comma missing at the end of a line?")
        for key in ("author", "title", "year"):
            if key not in fields or not fields[key]:
                raise BuildError(f"{where}: required field '{key}' is missing")
        if not isinstance(authors, list):
            raise BuildError(f"{where}: could not read the author field")
        year_s = str(fields["year"]).strip()
        if not re.fullmatch(r"\d{4}", year_s):
            raise BuildError(f"{where}: year must be four digits, got '{year_s}'")
        year = int(year_s)
        category = classify(e.entry_type, fields)
        if category == "other":
            warn(f"{where}: type @{e.entry_type} (or @misc without kind) is listed under 'Other'")
        if "theme" in fields:
            tid = str(fields["theme"]).strip()
            if tid not in themes_by_id:
                warn(f"{where}: theme '{tid}' is not in research.yml, ignoring it")
                fields.pop("theme")
        parts = []
        matched = set()
        for a in authors:
            slug = matcher.match(a)
            name = escape(author_display(a))
            if slug:
                matched.add(slug)
                name = Markup('<b class="us">') + name + Markup("</b>")
            parts.append(name)
        doi, url = ("", "")
        if fields.get("doi"):
            doi, url = doi_url(fields["doi"])
        link = str(fields.get("url", "")).strip()
        if link and not re.match(r"https?://", link, re.I):
            raise BuildError(f"{where}: url must start with http:// or https://, got '{link[:40]}'")
        pub = {
            "key": e.key,
            "entry_type": e.entry_type.lower(),
            "category": category,
            "year": year,
            "month": parse_month(fields.get("month")),
            "order": i,
            "fields": {k: (str(v) if not isinstance(v, list) else v) for k, v in fields.items()},
            "title": clean_text(fields["title"]),
            "authors_html": join_authors(parts),
            "people": sorted(matched),
            "doi": doi,
            "doi_url": url,
            "url": link,
            "openaccess": truthy(fields.get("openaccess", "")),
            "status": str(fields.get("status", "")).strip(),
            "note": linkify(clean_text(fields["note"])) if fields.get("note") else "",
            "abstract": clean_text(fields["abstract"]) if fields.get("abstract") else "",
            "theme": str(fields.get("theme", "")).strip(),
        }
        pub["venue_html"] = venue_html(pub)
        pub["cite_html"] = cite_html(pub)
        pubs.append(pub)

    # Newest first: year, then month (unknown month last), then later in the file first.
    pubs.sort(key=lambda p: (-p["year"], -(p["month"] or 0), -p["order"]))
    for p in pubs:
        if p["theme"]:
            themes_by_id[p["theme"]]["papers"].append(p)
    return pubs


def publications_by_year(pubs):
    """[(year, count, [(label, [pubs])...], [abstracts]), ...] newest first."""
    years = []
    for year, items in group_by_year(pubs, lambda p: p["year"]):
        groups = []
        for cat in CATEGORIES:
            if cat == "abstract":
                continue
            hits = [p for p in items if p["category"] == cat]
            if hits:
                groups.append((CATEGORY_LABEL[cat], cat, hits))
        abstracts = [p for p in items if p["category"] == "abstract"]
        count = len(items) - len(abstracts)
        years.append({"year": year, "count": count, "groups": groups, "abstracts": abstracts})
    return years


# ----------------------------------------------------------------------------
# Images
# ----------------------------------------------------------------------------

def square_crop(im):
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def normalise_mode(im):
    """Bring an image to RGB, RGBA or L so that resizing, palette reduction and
    JPEG saving work. Palette, greyscale-with-alpha and 16-bit PNGs (matplotlib,
    GMT, ImageJ) and CMYK JPEGs all arrive here."""
    if im.mode in ("RGB", "RGBA", "L"):
        return im
    if im.mode in ("P", "PA", "LA") or "transparency" in im.info:
        return im.convert("RGBA")
    if im.mode.startswith("I"):
        # 16-bit greyscale: scale to 8 bits rather than clipping at 255
        return im.convert("I").point(lambda v: v * (255 / 65535)).convert("L")
    return im.convert("RGB")


def save_png(im, dest, small=False, source_bytes=None):
    """Write a PNG. With small=True, use a 256-colour palette if the plain file
    would exceed PNG_MAX_BYTES, or if it comes out larger than the source it was
    resized from (source_bytes): a resized low-colour figure re-encoded as
    truecolour can double in size. Transparency is kept."""
    if small:
        im = normalise_mode(im)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        plain = buf.getvalue()
        if len(plain) <= PNG_MAX_BYTES and (source_bytes is None or len(plain) <= source_bytes):
            dest.write_bytes(plain)
            return
        q = im
        if q.mode == "RGBA" and q.getchannel("A").getextrema()[0] == 255:
            q = q.convert("RGB")   # no real transparency: the better quantiser applies
        q = q.quantize(256, dither=Image.Dither.FLOYDSTEINBERG)
        buf = io.BytesIO()
        q.save(buf, "PNG", optimize=True)
        quantised = buf.getvalue()
        # Keep the plain version when it is within the limit and the palette did not help.
        if len(plain) <= PNG_MAX_BYTES and len(quantised) >= len(plain):
            dest.write_bytes(plain)
        else:
            dest.write_bytes(quantised)
        return
    im.save(dest, "PNG", optimize=True)


def process_photos(content, out, people):
    folder = content / "photos"
    out_dir = out / "photos"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_slug = {p["slug"]: p for p in people}
    found = {}
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            slug = path.stem
            if slug not in by_slug:
                warn(f"{path}: no entry with slug '{slug}' in people.yml, photo skipped")
                continue
            found.setdefault(slug, path)   # .jpg wins over .png by sort order
    n = 0
    for slug, path in found.items():
        if not by_slug[slug]["url"]:
            continue   # a past intern without a page: nothing shows the photo
        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                if min(im.size) < PHOTO_SIZE:
                    warn(f"{path}: {im.size[0]}x{im.size[1]} px is smaller than the {PHOTO_SIZE} px "
                         f"output and will look soft; a larger photo would be better")
                im = normalise_mode(square_crop(im))
                if "A" in im.getbands():
                    # a cut-out with a transparent background goes on white, not black
                    flat = Image.new("RGB", im.size, (255, 255, 255))
                    flat.paste(im, mask=im.getchannel("A"))
                    im = flat
                else:
                    im = im.convert("RGB")
                im = im.resize((PHOTO_SIZE, PHOTO_SIZE), Image.LANCZOS)
                im.save(out_dir / f"{slug}.jpg", "JPEG", quality=PHOTO_QUALITY, optimize=True)
        except (OSError, ValueError) as e:
            raise BuildError(f"{path}: cannot read this image ({e})")
        by_slug[slug]["photo"] = f"/photos/{slug}.jpg"
        n += 1
    missing = [p["slug"] for p in people if not p["photo"] and p["group"] != "alumni"]
    if missing:
        warn("no photo for: " + ", ".join(missing) + " (placeholder with initials used)")
    return n


def process_logo(static, out):
    src = static / "logo.png"
    if not src.is_file():
        raise BuildError(f"{src}: the logo is missing")
    out_static = out / "static"
    out_static.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGBA")
        for name, size in LOGO_SIZES.items():
            out_im = im if im.size == (size, size) else im.resize((size, size), Image.LANCZOS)
            # Palette PNGs: the 240 px header logo drops from about 86 KB to 13 KB and the
            # 1080 px copy (used for link previews) from 1.2 MB to about 120 KB.
            save_png(out_im.quantize(256, dither=Image.Dither.FLOYDSTEINBERG), out_static / name)
        globe = im.crop(LOGO_GLOBE_BOX) if im.size == (1080, 1080) else square_crop(im)
        save_png(globe.resize((FAVICON_SIZE, FAVICON_SIZE), Image.LANCZOS).quantize(256),
                 out_static / "favicon.png")


def copy_static(static, out):
    """Copy static/ to _site/static/, resizing large figures under static/img/."""
    out_static = out / "static"
    out_static.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in sorted(static.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        rel = path.relative_to(static)
        if rel.as_posix() == "logo.png":
            continue   # written by process_logo
        if rel.as_posix() in STATIC_SKIP:
            continue   # kept in the repository, not published
        dest = out_static / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        if suffix in (".png", ".jpg", ".jpeg"):
            try:
                with Image.open(path) as im:
                    im = normalise_mode(ImageOps.exif_transpose(im))
                    w, h = im.size
                    resized = rel.parts[0] == "img" and max(w, h) > FIGURE_MAX
                    if resized:
                        im = im.resize(figure_output_size(w, h), Image.LANCZOS)
                    if suffix == ".png" and (resized or path.stat().st_size > PNG_MAX_BYTES):
                        save_png(im, dest, small=True,
                                 source_bytes=path.stat().st_size if resized else None)
                        n += 1
                        continue
                    if resized:
                        im.convert("RGB").save(dest, "JPEG", quality=88, optimize=True)
                        n += 1
                        continue
            except (OSError, ValueError) as e:
                raise BuildError(f"{path}: cannot process this image ({e})")
        shutil.copy2(path, dest)
        n += 1
    return n


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------

def placeholder_svg(person):
    text = escape(person["initials"])
    size = 56 if len(person["initials"]) > 1 else 64
    return Markup(
        '<svg class="photo placeholder" viewBox="0 0 160 160" role="img" '
        f'aria-label="{escape(person["name"])}, no photo yet">'
        '<circle cx="80" cy="80" r="80" fill="#e4f3f6"/>'
        f'<text x="80" y="82" text-anchor="middle" dominant-baseline="central" '
        f'font-family="-apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif" '
        f'font-size="{size}" font-weight="600" fill="#0d7a8c">{text}</text></svg>')


def photo_html(person, size=160, lazy=True):
    """The photo or the placeholder; lazy=False for the one photo at the top of a person page."""
    if person["photo"]:
        loading = ' loading="lazy"' if lazy else ""
        return Markup(
            f'<img class="photo" src="{escape(person["photo"])}" alt="{escape(person["name"])}" '
            f'width="{size}" height="{size}"{loading}>')
    return placeholder_svg(person)


def make_env(templates):
    env = Environment(
        loader=FileSystemLoader(str(templates)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["md"] = md
    env.filters["photo"] = photo_html
    env.filters["date"] = fmt_date
    env.filters["email_wbr"] = email_wbr
    return env


def email_wbr(email):
    """Let a long address wrap after the @ in a narrow card."""
    user, _, domain = str(email).partition("@")
    if not domain:
        return escape(email)
    return escape(user) + Markup("@<wbr>") + escape(domain)


def render_pages(env, out, site, data):
    today = dt.date.today()
    base = {
        "site": site,
        "pages": PAGES,
        "built": fmt_date(today),
        "year": today.year,
    }
    base.update(data)

    def page(template, path, title, description, **extra):
        ctx = dict(base)
        ctx.update({
            "page_path": path,
            "page_title": title,
            "page_description": description,
            "canonical": site["url"].rstrip("/") + path,
            "page_id": extra.pop("page_id", path.strip("/") or "home"),
        })
        ctx.update(extra)
        html_text = env.get_template(template).render(ctx)
        dest = out / path.strip("/") / "index.html" if path != "/" else out / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html_text, encoding="utf-8")

    name = site["name"]
    intros = site["page_intros"]

    def intro(key):
        return md(intros.get(key) or "")

    page("index.html", "/", f"{name}, {site['institute'] or 'IIT Gandhinagar'}",
         site["description"], page_id="home")
    page("research.html", "/research/", f"Research | {name}",
         "Research themes of the " + name + ".", intro=intro("research"))
    page("people.html", "/people/", f"People | {name}",
         "Members and alumni of the " + name + ".", intro=intro("people"))
    page("publications.html", "/publications/", f"Publications | {name}",
         "Papers, chapters, theses, datasets and preprints from the " + name + ".",
         intro=intro("publications"))
    page("news.html", "/news/", f"News | {name}",
         "News from the " + name + ".", intro=intro("news"))
    page("awards.html", "/awards/", f"Awards | {name}",
         "Awards, fellowships and prizes received in the " + name + ".", intro=intro("awards"))
    page("teaching.html", "/teaching/", f"Teaching | {name}",
         f"Courses taught by {data['pi']['name']} in the {site['department'] or 'Discipline of Earth Sciences'}, "
         f"{site['institute'] or 'IIT Gandhinagar'}.", intro=intro("teaching"))
    page("projects.html", "/projects/", f"Projects | {name}",
         "Funded projects of the " + name + ".", intro=intro("projects"))
    page("join.html", "/join/", f"{data['join_title']} | {name}",
         "How to join the " + name + " as a student, postdoc or intern.")
    page("contact.html", "/contact/", f"Contact | {name}",
         "How to reach the " + name + ".")

    # One page per person at /people/<slug>/ (see SCHEMA.md, content/people.yml).
    pi_name = data["pi"]["name"]
    for p in data["people"]:
        if not p["url"]:
            continue
        role = ROLE_PHRASE[p["role"]]
        if p["group"] == "alumni":
            role = "past " + role
        if p["affiliation_then"]:
            # from the PI's earlier group, never at IITGN: the head must not say otherwise
            description = f"{p['name']}, {role} with {pi_name}'s group at {p['affiliation_then']}."
        else:
            description = f"{p['name']}, {role} in the {name}, {INSTITUTE_SHORT}."
        page("person.html", p["url"], f"{p['name']} | {name}",
             with_topic(description, p["topic"]), page_id="people", person=p)


def with_topic(description, topic):
    """Append a member's topic line to the meta description while the whole stays within
    DESCRIPTION_MAX characters (search results cut at about 160); else the topic's first
    clause, if it is a real phrase; else the description alone."""
    topic = topic.strip().rstrip(".")
    if not topic:
        return description
    full = f"{description} {topic}."
    if len(full) <= DESCRIPTION_MAX:
        return full
    first = topic.split(",", 1)[0].strip()
    short = f"{description} {first}."
    if len(first.split()) >= 4 and len(short) <= DESCRIPTION_MAX:
        return short
    return description


def check_internal_links(out, site, themes, news, awards):
    """After rendering: every site-relative figure, news or award link must point
    at a page or file that was built, and its #fragment at an id on that page."""
    links = [(f["link"], f["where"]) for f in site["home"]["figures"]]
    for t in themes:
        links += [(f["link"], f["where"]) for f in t["images"]]
    links += [(n["link"], n["where"]) for n in news]
    links += [(a["link"], a["where"]) for a in awards]
    ids = {}
    for link, where in links:
        if not link or not link.startswith("/"):
            continue
        path, _, frag = link.partition("#")
        target = out / path.lstrip("/")
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            raise BuildError(f"{where}: link '{link}' points at nothing on the site")
        if frag:
            if target not in ids:
                found = ID_RE.findall(target.read_text(encoding="utf-8")) if target.suffix == ".html" else []
                ids[target] = set(found)
            if frag not in ids[target]:
                raise BuildError(f"{where}: link '{link}' names an anchor that is not on {path}")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def check_out_dir(out, content, static, templates):
    """Refuse an --out that is not a fresh folder or a previous build: it is
    deleted before the build, and '--out .' must not erase the repository."""
    for d in (HERE, content, static, templates):
        if out == d or out in d.parents:
            raise BuildError(f"--out {out} is the repository or one of its input folders; "
                             f"refusing to delete it. Use a separate folder such as _site")
    if not out.exists():
        return
    if not out.is_dir():
        raise BuildError(f"--out {out} is a file, not a folder")
    if (out / "build.py").exists() or (out / ".git").exists():
        raise BuildError(f"--out {out} contains build.py or .git; refusing to delete it")
    if any(out.iterdir()) and not (out / ".nojekyll").exists():
        raise BuildError(f"--out {out} is not empty and is not a previous build (no .nojekyll marker); "
                         f"refusing to delete it. Empty it yourself or choose another folder")


def build(content, static, templates, out):
    for d, label in ((content, "content"), (static, "static"), (templates, "templates")):
        if not d.is_dir():
            raise BuildError(f"{label} folder not found: {d}")
    check_out_dir(out, content, static, templates)

    site = load_site(content, static)
    people = load_people(content)
    people_by_slug = {p["slug"]: p for p in people}
    if site["pi"] not in people_by_slug:
        raise BuildError(f"{content / 'site.yml'}: pi '{site['pi']}' is not a slug in people.yml")
    themes = load_research(content, static, people_by_slug)
    themes_by_id = {t["id"]: t for t in themes}
    ongoing, completed = load_projects(content)
    courses = load_teaching(content)
    join_title, join_html = load_join(content)
    news = load_news(content, static, people_by_slug)
    awards = load_awards(content, people_by_slug)
    pubs = load_publications(content, NameMatcher(people), themes_by_id)

    # Output folder: start clean. The .nojekyll marker goes in first, so that a
    # build which stops half way still leaves a folder the next run may replace.
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / ".nojekyll").write_text("", encoding="utf-8")

    n_photos = process_photos(content, out, people)
    process_logo(static, out)
    n_static = copy_static(static, out)

    sections, alumni, interns_by_year = person_sections(people)
    attach_person_items(people, pubs, news, awards)
    home_pubs = [p for p in pubs if p["category"] in ("journal", "chapter")]
    data = {
        "pi": people_by_slug[site["pi"]],
        "people": people,
        "sections": sections,
        "alumni": alumni,
        "interns_by_year": interns_by_year,
        "themes": themes,
        "ongoing": ongoing,
        "completed": completed,
        "courses": courses,
        "join_title": join_title,
        "join_html": join_html,
        "news": news,
        "news_by_year": group_by_year(news, lambda n: n["date"].year),
        "home_news": news[: site["home"]["news_count"]],
        "awards": awards,
        "awards_by_year": group_by_year(awards, lambda a: a["year"]),
        "home_awards": awards[:3],
        "pubs": pubs,
        "pubs_by_year": publications_by_year(pubs),
        "home_pubs": home_pubs[: site["home"]["pubs_count"]],
        "n_pubs": sum(1 for p in pubs if p["category"] != "abstract"),
        "n_abstracts": sum(1 for p in pubs if p["category"] == "abstract"),
    }
    env = make_env(templates)
    render_pages(env, out, site, data)
    check_internal_links(out, site, themes, news, awards)

    n_pages = sum(1 for p in people if p["url"])
    print(f"built {out}: {len(people)} people ({n_pages} pages, {n_photos} photos), {len(themes)} themes, "
          f"{len(pubs)} publications, {len(news)} news items, {len(awards)} awards, "
          f"{len(courses)} courses, {len(ongoing) + len(completed)} projects, {n_static} static files")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the lab website into _site/.")
    ap.add_argument("--content", default=HERE / "content", type=Path)
    ap.add_argument("--static", default=HERE / "static", type=Path)
    ap.add_argument("--templates", default=HERE / "templates", type=Path)
    ap.add_argument("--out", default=HERE / "_site", type=Path)
    args = ap.parse_args(argv)
    try:
        build(args.content.resolve(), args.static.resolve(),
              args.templates.resolve(), args.out.resolve())
    except BuildError as e:
        print(f"\nbuild failed: {e}\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
