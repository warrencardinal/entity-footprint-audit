# Entity Footprint Audit — Check Personal Brand & Entity Profiles for SEO Consistency

A lightweight Python tool for auditing personal-brand and company profiles across the web. Checks status codes, redirects, titles, canonical tags, indexability, entity-name consistency and links back to a canonical domain.

I built this while cleaning up my own entity footprint and wanted a quick way to see which profiles were healthy, inconsistent, blocked, or dead without opening every URL by hand.

## What it checks

For each profile URL, the tool reports:

- HTTP status code
- Final URL after redirects
- Page title
- Canonical URL
- Whether the expected entity/person name appears on the page
- Whether the expected canonical domain appears in the HTML
- Whether the page appears indexable based on robots directives
- Whether an outbound link to the expected domain exists
- A simple `GOOD`, `FIX`, or `DEAD` result
- Notes about redirects, blocking, or `noindex` directives

## Install

After cloning or downloading the repository, install the two dependencies:

```bash
cd entity-footprint-audit
python -m pip install -r requirements.txt
```

Python 3.10+ is recommended.

## Usage

```bash
python audit.py example_profiles.csv
```

By default, results are written to:

```text
audit_results.csv
```

Choose a different output filename:

```bash
python audit.py profiles.csv --output my-audit.csv
```

Increase the request timeout if needed:

```bash
python audit.py profiles.csv --timeout 30
```

## Input CSV

Your CSV needs these four columns:

```csv
platform,url,expected_name,expected_domain
LinkedIn,https://www.linkedin.com/in/cardinal/,Warren Cardinal,warrencardinal.com
ORCID,https://orcid.org/0000-0003-0220-0463,Warren Cardinal,warrencardinal.com
YouTube,https://www.youtube.com/user/wcardinal,Warren Cardinal,warrencardinal.com
```

## Output

The output CSV includes:

```text
platform
input_url
status
final_url
page_title
canonical_url
name_found
domain_found
indexable
outbound_link
result
notes
```

Example:

```csv
platform,status,name_found,domain_found,indexable,outbound_link,result
LinkedIn,200,yes,yes,yes,yes,GOOD
ORCID,200,yes,yes,yes,yes,GOOD
YouTube,200,yes,no,yes,no,FIX
```

## How results are classified

`GOOD` means the page returned successfully and the expected name, canonical domain, indexability, and outbound link checks all passed.

`FIX` means the profile responded but one or more expected signals are missing, the page is non-indexable, or the site returned a blocking/error response such as `403` or `429`.

`DEAD` means the URL returned `404`/`410`, could not be reached, or failed before a usable response was received.

## Important limitation

Some major platforms actively block automated requests, require JavaScript, show different HTML to logged-out visitors, or rate-limit scripts. A `403`, `429`, missing title, or missing profile text does **not** always mean the public profile itself is broken. It may mean the platform did not serve the normal page to the auditor.

This tool is intended as a fast consistency check, not a replacement for manually reviewing important profiles.

## Why this exists

Search engines and AI systems increasingly resolve people and companies across many independent sources. When profiles use inconsistent names, dead URLs, old domains, or missing links, the overall entity footprint becomes harder to reconcile.

This tool gives you a quick first-pass audit of those signals.

## Roadmap

Possible additions:

- JSON-LD detection
- `Person` and `Organization` schema checking
- `sameAs` validation
- Profile image/headshot detection
- Entity-name variation detection
- HTML reports
- Bulk/concurrent URL checking
- Social profile consistency checks
- Optional schema/entity scoring

## Release

Initial release:

**v1.0.0 — Initial entity profile audit**

## License

MIT License. See [LICENSE](LICENSE).

## Author

Warren Cardinal  
https://warrencardinal.com/
