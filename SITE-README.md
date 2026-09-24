# Complete personal website

The redesigned website is now a complete static site. Local preview and GitHub Pages publish the **same** `_site` directory. No page relies on the old live website for its own content.

## Build and check

```sh
python -m pip install -r scripts/requirements-site.txt
python scripts/build_site.py
python scripts/check_site.py
node scripts/preview.cjs
```

Open http://127.0.0.1:4173/. If Python is not on PATH, set `SITE_PYTHON` to its executable path before starting the Node preview. This workspace also supports dependencies installed under `.build-deps`.

## Edit content

- `_includes/academic-home.html`: homepage text, project entries, selected research and navigation.
- `_layouts/academic-home.html`: shared document shell.
- `assets/css/academic-home.css`: shared homepage, archive and article styles.
- `_posts/*.md`: complete news originals, dates, local URLs and images.
- `_publications/*.md`: retained source reference only; not built or published. The complete publication list is on Google Scholar.
- `_portfolio/*.md`: research prototype images and details.
- `_teaching/*.md`: course records.
- `images/` and `files/`: public original media and downloads.

The existing Markdown/front-matter format is retained. New date values may be `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; precision is preserved in the display. News, portfolio and teaching permalinks are preserved. Homepage selected papers link to their external sources, and the full publication list links to Google Scholar. The former `/publications/` index redirects to Google Scholar; separate local publication records are no longer generated.

The old Jekyll templates remain in the source for reference, but the production workflow uses the Python static builder. Demo CV/talk/template content is not published as personal content. Only public collections and explicitly selected asset directories are copied; local source archives, scratch files, the supplied full CV PDF, scripts and dependency folders are excluded.

## Publish

The root file `85d24de9d58fae23945a5d596cb929cc.txt` is the public WeChat website verification file. The builder explicitly copies it to the published root on every deployment, including daily Scholar updates. Keep its filename and contents unchanged while the verification is in use.

After reviewing the site, publish the source to the repository's default branch and set GitHub Pages **Source = GitHub Actions**. `.github/workflows/pages.yml` installs the pinned build packages, refreshes the Scholar snapshot, builds and validates the complete site, and deploys `_site`.

Scholar refreshing is best effort: requests can be challenged, in which case the last verified snapshot and its original date remain. The page displays the last verified date. Check the workflow status in GitHub Actions after publishing; the site builder and link checker run before deployment.

### Google Scholar automatic updates

The updater supports the SerpApi Google Scholar Author API. Create a free account at https://serpapi.com/users/sign_up?plan=free, then add its API key as a repository Actions secret named `SERPAPI_API_KEY` (Settings > Secrets and variables > Actions > New repository secret). Never put the key in a source file, a commit, or browser JavaScript.

With this secret present, the daily workflow requests the author profile once through SerpApi, validates the author ID and all three lifetime metrics, then saves the snapshot and deploys it. Without the secret it falls back to a direct public-profile request, which Google may block. Errors preserve the last successful numbers and their original date. A successful website deployment does not by itself mean that the metrics refreshed: check the `Refresh Scholar snapshot` log for its outcome. To verify setup immediately, run this workflow manually from Actions > Publish website and refresh Scholar metrics > Run workflow.

The free plan currently includes 250 requests per month (checked 24 September 2026); daily requests use approximately 30–31, plus requests on website updates or manual runs. Check https://serpapi.com/pricing for current limits. No paid plan is required for this site's expected usage.
