# Case law data

Put the team's PakistanLawSite case law export in this folder.
The app reads every `.json`, `.jsonl` and `.csv` file here.

The app only uses cases that are in these files. If a user asks for a case
that isn't here, the app says it is not available. It never makes up a case.

## Format

Each case needs a **citation or title**, plus a **summary or the judgment text**.
Other fields are optional. Common column names are recognised automatically:

| Field | Accepted names |
|---|---|
| citation | citation, cite, case_citation, reference, case_no |
| title | title, case_title, parties, case_name |
| court | court, court_name |
| date | date, judgment_date, decided_on, year |
| judges | judges, bench, judge, coram |
| summary | summary, headnote, headnotes, abstract |
| text | text, judgment, content, full_text, body |
| url | url, link, source_url |

### JSON example (structure only)

```json
[
  {
    "citation": "<citation from the data>",
    "title": "<parties from the data>",
    "court": "<court>",
    "date": "<date>",
    "summary": "<headnote>",
    "text": "<judgment text>",
    "url": "<link to the source page>"
  }
]
```

After adding or changing files, there's no need to restart. The backend picks up changes automatically.
