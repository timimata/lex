# The page's Lighthouse runs

Lighthouse 13.5.0, mobile form factor with its simulated throttling (562.5 ms round trip,
1 474 kbps down), headless Chromium 1194, run against the built page (`web/dist`) served by the
API on a local port with a corpus made from the test fixtures and a scripted answer. So the
numbers measure the page itself, not Vercel's CDN or Gemini: a run against the deployed demo
is the next one to record.

```
npx lighthouse http://127.0.0.1:8766/ --only-categories=performance,accessibility,best-practices,seo --output=json
```

| Page | Performance | Accessibility | Best practices | SEO | FCP | LCP | TBT | CLS | Speed index |
|---|---|---|---|---|---|---|---|---|---|
| `/` before stage 6 | 93 | 100 | 100 | 100 | 2.4 s | 2.6 s | 110 ms | 0 | 2.4 s |
| `/resultados` before | 84 | 100 | 100 | 100 | 2.3 s | 2.4 s | 10 ms | 0.235 | 2.3 s |
| `/` after | 95 | 100 | 100 | 100 | 2.3 s | 2.5 s | 10 ms | 0 | 2.3 s |
| `/resultados` after | 94 | 100 | 100 | 100 | 2.4 s | 2.6 s | 10 ms | 0 | 2.4 s |

What stage 6 changed between the two runs: the Results and About pages load on demand (5.8 kB
and 1.3 kB of their own, the main script 266.7 kB, 84.4 kB gzipped, most of it React), and the
main area fills the first screen, so the leaderboard arriving after its fetch no longer moves
the footer into view and out again (the 0.235 layout shift). The page loads no font.

What the remaining 2.3 s of first paint is: the script, on a simulated 4G connection. Lighthouse
lists nothing else. Bringing it down would mean a smaller framework or server-rendered HTML,
which is not planned (web/ROADMAP.md).

The colour contrast of every pair the page draws is in [web-contrast.md](web-contrast.md).

## 2026-10-06: Preact instead of React (web/ROADMAP.md, stage 7)

The same Lighthouse 13.5.0 and command, run on this machine (Chromium 1243 from Playwright) against
the page served by `web/e2e.py`'s server: the real corpus and a scripted answer. The "before" rows
are today's build, measured again here, and match 2026-10-02's within 0.1 s.

| Page | Main script | Performance | Accessibility | Best practices | SEO | FCP | LCP | TBT | CLS | Speed index |
|---|---|---|---|---|---|---|---|---|---|---|
| `/` before | 268.7 kB, 85.2 kB gzipped | 95 | 100 | 100 | 100 | 2.3 s | 2.5 s | 0 ms | 0 | 2.3 s |
| `/resultados` before | | 94 | 100 | 100 | 100 | 2.4 s | 2.6 s | 0 ms | 0 | 2.4 s |
| `/` after | 67.6 kB, 24.7 kB gzipped | 100 | 100 | 100 | 100 | 1.4 s | 1.5 s | 0 ms | 0 | 1.4 s |
| `/resultados` after | | 99 | 100 | 100 | 100 | 1.5 s | 1.7 s | 0 ms | 0 | 1.5 s |

The components are unchanged and still type-checked against React's types; Vite aliases React
to `preact/compat` (10.29.8) when it bundles. Stage 6's bar of 1.5 s to first paint is met on the
home page and reached on the results page.
