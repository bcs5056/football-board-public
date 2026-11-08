# Football Betting Board (public)

Live site: https://bcs5056.github.io/football-board-public/

Everything here is updated automatically by a Claude scheduled task each morning:

| Path | What it is |
|---|---|
| `index.html` | The site, built by `scripts/build_site.py` from `data/` |
| `data/*.json` | The five public datasets (slate, NFL/college games, NFL/college splits) |
| `post/card.png`, `post/post.txt` | Today's X image and post text |
| `posted/<date>.json` | Log of what went out to X (one post per day max) |

## Posting to X

`.github/workflows/post-to-x.yml` runs whenever `post/` changes and posts to X with these
repository secrets (Settings → Secrets and variables → Actions → **New repository secret**):

- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

Until all four exist, the workflow skips posting. To pause posting without deleting secrets,
add a repository **variable** `X_POSTING_PAUSED` = `true`. To post by hand, open
Actions → "Post daily card to X" → Run workflow.

For entertainment only. 21+. Gambling problem? Call 1-800-GAMBLER.
