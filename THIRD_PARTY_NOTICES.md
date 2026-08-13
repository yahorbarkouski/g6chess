# Third-party notices

G6 depends on third-party software and data. The lockfiles are the authoritative
version inventory; this file calls out components with material runtime or
redistribution obligations.

- **Stockfish** — GPL-3.0. The backend invokes a system executable. The frontend
  redistributes `stockfish@18.0.8` JavaScript/WASM built from
  [`93c9945`](https://github.com/nmrugg/stockfish.js/tree/93c994592dcf3b4b21052ab925e9b534df9c0918).
  Its GPL text and source reference are shipped beside the browser assets.
- **python-chess (`chess`)** — GPL-3.0-or-later, used in-process by the backend.
- **Lichess chess openings** — CC0-1.0. G6 pins revision
  `4b8622759e7ae6f93f011cc6c83a3823401ab45e` and verifies each TSV digest.
- **Maia 2** — model code and weights are optional runtime dependencies and are
  not stored in this repository. Review upstream terms before redistributing
  model artifacts.

Dinamo trial and purchased font binaries are intentionally not distributed;
the interface uses system font fallbacks.
