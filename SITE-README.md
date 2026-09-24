# Complete personal website

The redesigned website is now a complete static site. GitHub Pages publishes `_site`; local preview serves the same public build and adds the owner's local BD-RIS notes in memory. The notes are never written to `_site`. No page relies on the old live website for its own content.

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
- `assets/js/bd-ris-model.js`: pure eight-element, lossless near/far illumination and S-parameter comparison model. Reflection compares diagonal R with fully connected reciprocal unitary R. Transmission compares diagonal T with non-diagonal unitary T; both are lifted to reciprocal 16-port S matrices. Both designs optimise the same target-power / mean-sidelobe-region objective. The separate paired example has eight independent two-port groups and R/T/hybrid steering. Run `node scripts/test_bd_ris.cjs` after changes.
- `assets/js/bd-ris-demo.js`: compact browser controls, common-scale beam plots, matrix displays and direction markers. Both scripts are fingerprinted by the builder and have no external dependencies or API requests.
- `local/bd-ris-method.html`: the owner's expandable **Assumptions, method & references** notes. The existing `local/` Git ignore rule keeps this file out of source commits. Only `scripts/preview.cjs`, bound to `127.0.0.1`, inserts it into the local homepage response; the public build, page source and deployment artifact omit it. Keep a private backup when moving to another computer. There is no online owner login: even the owner must use local preview to open this section. The public demo code and its short illustrative-model notice remain public.
- `_posts/*.md`: complete news originals, dates, local URLs and images.
- `_publications/*.md`: retained source reference only; not built or published. The complete publication list is on Google Scholar.
- `_portfolio/*.md`: research prototype images and details.
- `_teaching/*.md`: course records.
- `images/` and `files/`: public original media and downloads.

The existing Markdown/front-matter format is retained. New date values may be `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; precision is preserved in the display. News, portfolio and teaching permalinks are preserved. Homepage selected papers link to their external sources, and the full publication list links to Google Scholar. The former `/publications/` index redirects to Google Scholar; separate local publication records are no longer generated.

The old Jekyll templates remain in the source for reference, but the production workflow uses the Python static builder. Demo CV/talk/template content is not published as personal content. Only public collections and explicitly selected asset directories are copied; local source archives, scratch files, the supplied full CV PDF, scripts and dependency folders are excluded.

The opening section shows the portrait and a short introduction on the right. The BD-RIS demonstration follows Research, with controls and plots side by side on desktop and stacked on smaller screens. The local BD-RIS preview opens with **Near field**, **Reflection**, and **Sidelobe suppression**. Near/far illumination is shared across both tabs. Every illumination supports reflection and transmission beam steering. The primary tab overlays phase-only and joint amplitude–phase solutions under the same aperture, captured input power, target, guard sector and objective. **Target power** removes the sidelobe penalty; **Sidelobe suppression** trades target power against mean power outside a fixed guard, rather than imposing a taper. D uses multi-start phase optimisation, not a fixed phase-aligned comparator. A suppression optimum may shift its actual peak slightly; the green ray marks the requested target. The **Back-to-back pairs** tab retains independent R/T steering and the split control. Source position, numerical readouts, full S matrices and methods are folded by default. The default panel explicitly identifies the model as illustrative.

After changing the BD-RIS model or its assumptions, also run `node scripts/audit_bd_ris.cjs`. The current audit sweeps all 111 target-angle settings in every illumination / operation / objective combination, near-source distance steps and source-angle boundaries, and all suppression weights at centre/edge targets (1,194 comparison states), plus 666 paired states. Unit checks cover the spherical-to-plane-wave limit, analytic array factors and coherent bounds, phase-only optimisation, the Hermitian eigensolver, reciprocal synthesis, common objectives, and both-sided power conservation. Numerical consistency is not full-wave or hardware validation. Earlier four-port model files and tests are retained only as local backups under `tmp/bd-ris-before-near-far/`.

The active visual theme is **Modern Collegiate**: a deep teal navigation bar and academic-journey strip, serif headings, a portrait on the right, and three research columns on desktop. The final `.collegiate-site` rules in `assets/css/academic-home.css` apply consistently to the homepage and the complete archive/detail pages. All content, the embedded BD-RIS lab, Scholar refresh and MapMyVisitors integration are retained; older news and projects remain expandable.

## Publish

The root file `85d24de9d58fae23945a5d596cb929cc.txt` is the public WeChat website verification file. The builder explicitly copies it to the published root on every deployment, including daily Scholar updates. Keep its filename and contents unchanged while the verification is in use.

After reviewing the site, publish the source to the repository's default branch and set GitHub Pages **Source = GitHub Actions**. `.github/workflows/pages.yml` installs the pinned build packages, refreshes the Scholar snapshot, builds and validates the complete site, and deploys `_site`.

Scholar refreshing is best effort: requests can be challenged, in which case the last verified snapshot and its original date remain. The page displays the last verified date. Check the workflow status in GitHub Actions after publishing; the site builder and link checker run before deployment.

### Google Scholar automatic updates

The updater supports the SerpApi Google Scholar Author API. Create a free account at https://serpapi.com/users/sign_up?plan=free, then add its API key as a repository Actions secret named `SERPAPI_API_KEY` (Settings > Secrets and variables > Actions > New repository secret). Never put the key in a source file, a commit, or browser JavaScript.

With this secret present, the daily workflow requests the author profile once through SerpApi, validates the author ID and all three lifetime metrics, then saves the snapshot and deploys it. Without the secret it falls back to a direct public-profile request, which Google may block. Errors preserve the last successful numbers and their original date. A successful website deployment does not by itself mean that the metrics refreshed: check the `Refresh Scholar snapshot` log for its outcome. To verify setup immediately, run this workflow manually from Actions > Publish website and refresh Scholar metrics > Run workflow.

The free plan currently includes 250 requests per month (checked 24 September 2026); daily requests use approximately 30–31, plus requests on website updates or manual runs. Check https://serpapi.com/pricing for current limits. No paid plan is required for this site's expected usage.
