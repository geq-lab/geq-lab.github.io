# How to update the site

Everything on https://geq-lab.github.io/ comes from a few text files in the `content/` folder of this repository. You edit them on github.com in your browser, commit, and the site rebuilds itself in about a minute. Nothing needs to be installed on your laptop.

You need to be a member of the `geq-lab` organisation on GitHub with write access to this repository. Ask Utsav if you are not.

## Editing a file on github.com

1. Open the file in the repository on github.com, for example `content/people.yml`.
2. Click the pencil icon ("Edit this file") at the top right of the file view.
3. Make your change in the editor.
4. Click "Commit changes...", write one line saying what you did ("add myself to people"), keep "Commit directly to the main branch" selected, and click "Commit changes".

That is all. The build starts on its own.

## Add yourself

Open `content/people.yml`. It is a list; each person is a block that starts with `- slug:`. Copy an existing block from the same section (PhD students, say) and change the fields. Indentation matters: two spaces, no tabs. Keep the dash before `slug:`; without it your block silently merges into the person above and the build stops with a message about the slug count.

```yaml
- slug: priya-nair                 # lower-case, hyphens, no spaces; this names your photo file
  name: Priya Nair
  role: PhD student                # exactly one of: Principal Investigator, Postdoctoral fellow,
                                   # Research staff, PhD student, MTech student, Visiting scholar, Intern
  group: current                   # current, visiting or alumni
  since: Jul 2026                  # a year, or "Jul 2026"
  topic: Ground-motion models for the Himalaya
  email: priya.nair@iitgn.ac.in    # IITGN address only, leave out if you do not want it shown
  cosupervisor: Harini Subramanian, IITGN   # optional
  links: {scholar: "https://scholar.google.com/citations?user=XXXX", github: "https://github.com/priya"}   # optional
```

Put URLs inside quotes, as above; if YAML refuses a value with a `?` or a `:` in it, quotes are the fix.

Then add a photo. Go to the `content/photos/` folder on github.com, click "Add file" then "Upload files", and upload a picture named after your slug, in lower case and exactly as the slug is spelt: `priya-nair.jpg` (or `.png`; `Priya-Nair.JPG` is skipped with only a warning in the build log). Any size and shape is fine, but at least 500 px on the short side looks sharp; the build turns it into a square at 480 px, cropping to the centre, so a head-and-shoulders picture with some room around the head works best. Until a photo arrives the page shows your initials in a circle.

When you leave, change `group: current` to `group: alumni`, add `until: 2029` and, if you like, `degree: PhD Earth Sciences, IITGN, 2029` and `now: Postdoc, University of X` (only if you want that public). The alumni list is sorted by `until`.

## Add a news item

News items are one file each in `content/news/`. On github.com open that folder, click "Add file" then "Create new file", and name it with the date and a few words: `2026-11-03-egu-abstracts.md`. Paste this and fill it in:

```
---
title: Three abstracts accepted for EGU 2027
date: 2026-11-03
link: https://meetingorganizer.copernicus.org/...    # optional
people: [omkar, saurabh-choubey]                     # optional, slugs from people.yml
---
Omkar, Saurabh and Utsav will present in Vienna in April. One to three plain sentences are enough.
```

Keep the three dashes exactly as shown, above and below the header. The date is `YYYY-MM-DD`. The newest item goes to the top of the News page and the home page shows the five most recent. If you name someone in `people:`, the slug must exist in `people.yml` or the build will stop and tell you so.

## Add a paper

Papers live in `content/publications.bib`, one BibTeX entry each. Open the file, scroll to the end, and paste a new entry.

The easiest way to get the entry is from the DOI: go to https://doi.org/ , paste the DOI in the box, open the article page, and use the journal's "Cite" or "Export citation" button, choosing BibTeX. Google Scholar also gives one through the quote mark under a result, then "BibTeX". Paste what you get, then tidy it so that it looks like the entries already in the file:

```bibtex
@article{nair2027himalaya,
  author  = {Nair, Priya and Mannu, Utsav},
  title   = {A ground-motion model for the Himalaya},
  journal = {Bulletin of the Seismological Society of America},
  year    = {2027},
  volume  = {117},
  number  = {2},
  pages   = {451--470},
  doi     = {10.1785/0120260001},
  openaccess = {true},
  theme   = {statseis},
}
```

Things to check:

- Authors are written `Surname, Given and Surname, Given`. Someone with a single name is written `{Omkar}` in braces.
- The citation key (`nair2027himalaya`) is surname, year, one word from the title, and must not repeat an existing key.
- `author`, `title` and `year` are required. Every field ends with a comma.
- `doi` is just the DOI (`10.1785/...`), not the full URL. The build makes the link.
- Entry types: `@article` for journal papers, `@incollection` for book chapters, `@inproceedings` for conference papers (add `abstract_only = {true}` for a conference abstract), `@phdthesis` and `@mastersthesis` for theses, `@misc` with `kind = {dataset}` or `kind = {preprint}` for those.
- Optional fields the site understands: `openaccess = {true}` (the publisher's version is free to read), `theme = {...}` with one of the five ids from `content/research.yml` (`wedges`, `rifts`, `statseis`, `hazard`, `deep`), so the paper also appears under that theme on the Research page (an unknown id is dropped with only a warning in the build log), `status = {in press}` or `{under review}`, and `abstract = {...}`, which is shown folded under the entry.

Names of group members are shown in bold automatically, matched on surname and first initial against `people.yml`.

## What happens next

A minute or so after you commit, the site is rebuilt and published. To watch it, open the "Actions" tab of the repository on github.com. The newest run is at the top; a green tick means the site is live, a red cross means the build stopped. Click the red run, then the "build" job, and read the last lines: the message names the file and the problem, for example `content/people.yml 'priya-nair': role 'PhD' is not one of: ...`. Fix the file and commit again.

If a page looks wrong after a green run, reload it; browsers cache the old version for a while.

## Running the build on your own computer

Not needed for normal edits, but handy for checking a large change before committing.

```
git clone https://github.com/geq-lab/geq-lab.github.io.git
cd geq-lab.github.io
pip3 install -r requirements.txt
python3 build.py
python3 -m http.server -d _site
```

On Windows the commands are usually `pip` and `python`. Then open http://localhost:8000/ in a browser. Run `python3 build.py` again after each edit. The `_site/` folder is generated and is not committed.
