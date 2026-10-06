# The page's colour contrast

Produced by `python web/contrast.py --md docs/checks/web-contrast.md` from the tokens in `web/src/styles.css`: every pair of colours the page draws, in the light and the dark scheme, against the WCAG 2.2 bar for it (4.5:1 for text, 3:1 for large text, field borders and the focus ring). Opacities are folded into the foreground.

| Pair | Light | Dark | Bar |
|---|---|---|---|
| body text on paper | 15.32 | 14.67 | 4.5 |
| secondary text on paper | 8.98 | 10.71 | 4.5 |
| muted text on paper | 5.88 | 6.10 | 4.5 |
| muted text on paper-2 (the reader, the basis) | 6.41 | 5.66 | 4.5 |
| muted text on paper-3 (the footer) | 5.32 | 5.17 | 4.5 |
| notice on paper-3 | 8.14 | 9.07 | 4.5 |
| links on paper | 7.24 | 8.51 | 4.5 |
| links on paper-2 | 7.89 | 7.89 | 4.5 |
| links on paper-3 (the footer) | 6.56 | 7.20 | 4.5 |
| refusal and removed text on paper | 5.13 | 8.04 | 4.5 |
| removed text on paper-2 (the reader) | 5.59 | 7.45 | 4.5 |
| button text on cobalt | 7.89 | 8.51 | 4.5 |
| button text on cobalt-strong (hover) | 10.25 | 11.56 | 4.5 |
| wordmark and nav on the header | 9.40 | 13.95 | 4.5 |
| nav links at 85% on the header | 7.25 | 10.30 | 4.5 |
| language switch at 80% on the header | 6.62 | 9.23 | 4.5 |
| field border on paper | 3.65 | 3.74 | 3.0 |
| field border on paper-2 | 3.98 | 3.46 | 3.0 |
| focus ring (cobalt) on paper | 7.24 | 8.51 | 3.0 |
| focus ring (cobalt) on paper-2 | 7.89 | 7.89 | 3.0 |
| the share bar (cobalt) on its track | 5.27 | 5.88 | 3.0 |
