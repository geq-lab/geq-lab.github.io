# Site contract: layout, data files and build

Repository for https://geq-lab.github.io/ , the Geodynamics & Earthquake Lab, Earth Sciences, IIT Gandhinagar. Everyone who edits this repository (people and agents) follows this file. The build (`build.py`) reads `content/` and `static/`, renders `templates/`, and writes `_site/`, which GitHub Pages serves. Nothing in `_site/` is committed.

## Layout

```
build.py                 generator (Python 3.11+, see requirements.txt)
requirements.txt         jinja2 pyyaml markdown bibtexparser>=2 Pillow
.github/workflows/pages.yml   build on push to main and deploy to GitHub Pages
HOWTO.md                 one page for students: add yourself, a news item, a paper
README.md                what the site is, how to build locally
SCHEMA.md                this file
content/site.yml         site-wide text and contact details
content/people.yml       everyone, current and past
content/research.yml     the research themes
content/projects.yml     funded projects
content/teaching.yml     courses
content/awards.yml       awards, fellowships and prizes (optional)
content/join.md          the Join us page (Markdown)
content/publications.bib papers, chapters, conference papers, theses, datasets, preprints, abstracts
content/news/YYYY-MM-DD-slug.md   one file per news item
content/photos/<slug>.jpg|png     raw member photos, any size (build crops to a square)
static/style.css         the one stylesheet
static/logo.png          lab logo (1080x1080); static/logo_green.png is the alternative colouring
static/img/              the group's own figures only, each credited where used
templates/*.html         Jinja2 templates: base.html plus one per page
_site/                   generated output (git-ignored)
```

Output URLs (folder style): `/` (home), `/research/`, `/people/`, `/publications/`, `/news/`, `/awards/`, `/teaching/`, `/projects/`, `/join/`, `/contact/`. Assets at `/static/...`, member photos at `/photos/<slug>.jpg`. The build writes `_site/.nojekyll`.

## content/site.yml

```yaml
name: Geodynamics & Earthquake Lab
short_name: GEQ Lab
institute: Indian Institute of Technology Gandhinagar
department: Discipline of Earth Sciences
url: https://geq-lab.github.io/
description: one sentence for the <meta name=description> and the home page
pi: utsav-mannu                     # slug in people.yml
contact:
  email: utsav.mannu@iitgn.ac.in
  phone: "+91 79 2395 2589"          # office line only
  address:                           # list of lines
    - Academic Block 12, Room 406-B
    - Indian Institute of Technology Gandhinagar
    - Palaj, Gandhinagar, Gujarat 382355, India
  map_url: https://maps.app.goo.gl/...   # optional
links:                               # shown in the footer, in this order; quote any URL (a ? or : inside {} breaks YAML)
  - {label: IITGN faculty page, url: "https://iitgn.ac.in/faculty/earths/fac-utsav"}
  - {label: Google Scholar, url: "https://scholar.google.com/citations?user=hcisl7UAAAAJ"}
  - {label: ORCID, url: "https://orcid.org/0000-0003-2416-3958"}
  - {label: GitHub, url: "https://github.com/geq-lab"}
home:
  intro: |                           # Markdown, two or three short paragraphs: who we are, what we do, where
  figures:                           # 4 to 8 of the group's own research figures, shown as a grid under the intro
    - image: img/wedge_model_t135.png      # under static/
      alt: Cross-section of a numerical accretionary wedge model
      caption: Accretionary wedge after 4 million years of convergence, WedgeFlow model   # one line, plain
      credit: Geodynamics & Earthquake Lab   # required; for a figure from one of our open-access papers, "Figure 3 of Sharma et al. (2025), CC BY 4.0"
      link: /research/#wedges              # optional, where a click goes (a research theme, a news item, a DOI); without it the figure opens the full-size image
  news_count: 5
  pubs_count: 5
contact_text: |                      # Markdown, a short paragraph for the contact page (how to reach, visiting)
footer_note: "Earth Sciences, IIT Gandhinagar"   # optional
page_intros:                         # optional Markdown, one short paragraph shown under the page heading
  research: |
  people: |
  publications: |
  news: |
  awards: |
  teaching: |
  projects: |
facilities:                          # shown at the end of the Research page
  - {name: Raspberry Shake RS3D seismometers (two), note: short-period three-component, since Feb 2024}
  - {name: PARAM Ananta, note: IITGN's supercomputer, used for the geodynamic and DFT work}
```

## content/people.yml

A list. Order within a group is the display order (the build also sorts current members by role rank, then by `since`).

```yaml
- slug: utsav-mannu            # lowercase, hyphenated; photo file is content/photos/<slug>.jpg or .png
  name: Utsav Mannu
  role: Principal Investigator # exactly one of: Principal Investigator, Postdoctoral fellow, Research staff,
                               # PhD student, MTech student, Visiting scholar, Intern
  group: current               # current | visiting | alumni
  title_line: Assistant Professor, Earth Sciences, IIT Gandhinagar   # optional, one line
  since: 2021                  # year, or "Jul 2023"
  until: 2026                  # alumni only
  degree: MTech Earth System Science, IITGN, 2026   # alumni only, optional: what they finished here
  now: PhD student, ...        # alumni only, optional: where they went, only if public
  topic: one line, what they work on
  email: name@iitgn.ac.in      # optional, institutional addresses only
  cosupervisor: Harini Subramanian, IITGN   # optional
  links: {scholar: "URL", orcid: "URL", github: "URL", website: "URL", linkedin: "URL"}   # optional; quote the URLs
  bio: |                       # optional Markdown paragraph (PI, postdocs)
```

Sections on the People page: Faculty; Postdoctoral fellows and research staff; PhD students; MTech students; Visiting scholars; Alumni (by `until` descending; interns listed as one compact line per year). A member without a photo gets a placeholder with initials; the build never fails for a missing photo.

## content/research.yml

```yaml
- id: wedges                   # short id, used as the anchor /research/#wedges and in publications.bib `theme`
  title: Subduction wedges and forearc basins
  summary: |                   # Markdown, about 120 to 180 words, plain language, no slogans
  image: img/wedge_model_t135.png          # optional, under static/: the lead figure of the theme
  image_alt: Cross-section of a numerical wedge model
  image_caption: one plain line shown under the lead figure   # optional
  image_credit: WedgeFlow model output, Geodynamics & Earthquake Lab   # required when image is set; the credit alone, the description goes in image_caption
  images:                                  # optional, further figures shown as a row of thumbnails after the text
    - {image: img/xxx.png, alt: ..., caption: ..., credit: ..., link: ...}   # link optional; a figure without one opens the full-size image, and so does the lead figure
  people: [saurabh-choubey, utsav-mannu]   # slugs; the build links them to the People page
```

Figures anywhere on the site are the group's own (model outputs, maps, field photographs, posters) or figures from the group's own open-access papers (CC BY), each with a credit line; nothing from other people's papers, textbooks or the web. Figures must not show or name industry clients or their sites.

## content/projects.yml

```yaml
- title: Full project title
  agency: DST                  # funding agency or scheme; no industry client names on this site
  role: PI                     # PI | Co-PI | Fellow | Mentor
  years: 2018 to 2023
  status: completed            # completed | ongoing
  note: one line, optional
```

## content/awards.yml

Every award, fellowship, prize, medal, best-paper or best-poster award, competitive travel grant and formal distinction received by the PI or by a member while in the group (and the PI's earlier ones). Rendered at `/awards/` newest first, grouped by year (dated entries before undated ones within a year), and the three latest on the home page under the news. Nominations and applications that did not result in an award are not listed. The file is optional: without it the Awards page says "Nothing here yet".

```yaml
- year: 2025
  date: 2025-01-04            # optional, exact date if known
  who: [utsav-mannu]          # slugs from people.yml (linked to the People page), or a plain name in quotes for someone outside the group
  title: Alumni Award, IISER Kolkata
  giver: IISER Kolkata        # the body that gave it
  for: optional, one line on what it was for
  link: https://...           # optional
```

## content/teaching.yml

```yaml
- code: EH 610
  title: Engineering Seismology and Seismic Hazard Analysis
  level: PG                    # UG | PG | UG/PG
  offered: [2022-23 II, 2024-25 II]   # semesters taught, oldest first; optional
  link: https://...            # course plan or page, optional
  note: one line, optional
```

## content/news/YYYY-MM-DD-slug.md

```
---
title: Short title in sentence case
date: 2026-06-10
link: https://doi.org/...      # optional
image: img/some_figure.png     # optional, under static/
image_caption: one plain line shown under the figure   # optional
image_credit: Geodynamics & Earthquake Lab   # required when image is set; the build stops without it
people: [omkar]                # optional slugs
---
One to three plain sentences. Markdown allowed. No marketing language.
```

The News page lists all items newest first, grouped by year; the home page shows the latest `news_count`.

## content/publications.bib

Standard BibTeX. Entry types used: `@article` (journal), `@incollection` or `@inbook` (chapter), `@inproceedings` (conference paper or abstract), `@phdthesis`, `@mastersthesis`, `@misc` (dataset or preprint). Fields: `author`, `title`, `journal` or `booktitle`, `year`, `month`, `volume`, `number`, `pages`, `doi`, `url`, `publisher`, `school`, `note`. Extra fields the build understands:

- `kind = {dataset}` or `kind = {preprint}` on `@misc`
- `abstract_only = {true}` on `@inproceedings` for conference abstracts (listed in a collapsed section)
- `openaccess = {true}` adds an open-access mark
- `theme = {wedges}` ties the entry to a research theme id
- `status = {in press}` or `{under review}` (shown instead of volume/pages)

Authors as `Surname, Given and Surname, Given`; a mononym as `{Omkar}`. The build groups entries by year (newest first), orders journal papers, chapters, conference papers, theses, datasets and preprints, then the collapsed abstracts, and bolds the names of everyone in people.yml. Citation keys: `surnameYYYYword`.

## Build behaviour

- `python build.py` renders everything into `_site/` in under a few seconds (`--content DIR`, `--static DIR`, `--templates DIR` and `--out DIR` override the defaults, so a test can run on fixture content); it exits non-zero with a clear message on a malformed YAML or BibTeX file, a missing required field, a `people:` slug that is not in people.yml, a figure without a credit, or a site-relative `link` (figure, news item or award) that points at a page or anchor the build did not produce.
- Photos: `content/photos/<slug>.(jpg|jpeg|png)` are EXIF-rotated, centre-cropped to a square and saved as `_site/photos/<slug>.jpg` at 480x480, quality 85. The logo is written at 1080, 240 and 64 px (`_site/static/logo.png`, `logo-240.png`, `favicon.png`). Figures under `static/img/` larger than 1600 px on the long side are resized to 1600 on output.
- Markdown via `markdown` with `extra` and `sane_lists`; links open in the same tab; no raw HTML needed by editors.
- Every page: `<title>`, `<meta name=description>`, `<meta name=viewport>`, canonical URL, the favicon, `<nav>` with the nine pages, a footer with the institute line and links.
- No external JavaScript, no analytics, no web fonts, no tracking. One small inline script at most (for the abstracts toggle, or none: use `<details>`).

## Look

Academic, not corporate: it should read like a university research group page. White background, content column `max-width: 60rem`, 1 rem side gutters, system font stack (`-apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`), body 17 px line-height 1.55, headings in deep slate `#1F3D47`, text links in the darker teal `#0d7a8c` (5:1 on white; `#0a6273` on hover) with the logo teal `#14A4BC` only as an accent (active nav underline, open-access mark), thin rules `#dde3e6`, no hero banner, no cards with shadows, no icons for their own sake. Header: logo at 56 px tall on the left, the lab name beside it as plain text, then the nav as a horizontal list that wraps on narrow screens. People: a grid of 160 px photos (circle or rounded square) with name, role and topic beneath; alumni as a plain list. Publications: a numbered-free list grouped by year, authors then title in italics then venue, DOI as a link. Works on a phone at 360 px wide with no horizontal scroll, prints cleanly. Dark mode is not required.

## Deployment

`.github/workflows/pages.yml`: on push to `main` and on `workflow_dispatch`; permissions `contents: read`, `pages: write`, `id-token: write`; job `build` (`actions/checkout@v6`, `actions/setup-python@v6` with 3.12, `pip install -r requirements.txt`, `python build.py`, `actions/configure-pages@v5`, `actions/upload-pages-artifact@v4` with `path: _site`), job `deploy` (`actions/deploy-pages@v4`, environment `github-pages`, concurrency group `pages` with `cancel-in-progress: false`). Pages source in the repository settings: GitHub Actions (one-time). PNG figures over 300 KB, and resized PNGs that would otherwise come out larger than their source, are written with a 256-colour palette; a local preview must be served over HTTP (`python -m http.server -d _site`) for root-relative paths to resolve.

## House rules for content

- Plain, direct prose in the group's own voice. No slogans, no "cutting-edge", "state-of-the-art", "vibrant", "passionate", "unravel", no exclamation marks, no emoji. Prefer "we" to "the lab". Sentence case in headings.
- No industry client or site names anywhere (not NTPC, Adani, APL, APCO, GCL, Zydus, Grace Energy, GSPC, CIL, nor plant or site names); industry work is described generically as sponsored site evaluation and ground-motion studies for critical facilities. Government agencies and schemes (DST, SERB, ANRF, PMRF, NIDM, MoES, IITGN) may be named.
- No phone numbers except the office line; no personal matters (stipends, leave, health, family); no unsubmitted or under-review paper titles unless marked `status = {under review}` deliberately; no third-party figures; every figure credited.
- Only institutional email addresses, and only for people who have one listed.
