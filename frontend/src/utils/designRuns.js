/**
 * designRuns — the run history carried by the /results page.
 *
 * Every design (the first one, and each re-run with tuned parameters) is a run:
 *   { id, params, results }   params = the exact body POSTed to /api/design
 *
 * The list lives in the router's location.state, so it survives a reload of the
 * results page and the browser's back/forward, but not a new session — runs
 * are a scratchpad for comparing parameter choices, History keeps the record.
 */

/** In-memory draft key shared by the designer and the results page. */
export const DESIGN_DRAFT_KEY = 'designDraft.formData';

/** Oldest runs are dropped beyond this, so the switcher stays one line. */
export const MAX_RUNS = 8;

export function firstRunState(params, results) {
  return { runs: [{ id: 1, params, results }], activeId: 1 };
}

/**
 * Normalise router state into { runs, activeId }. Accepts the legacy
 * { results, params } shape (History page, links saved before run history).
 */
export function readRunsState(state) {
  if (state?.runs?.length) {
    const ids = state.runs.map((r) => r.id);
    return { runs: state.runs, activeId: ids.includes(state.activeId) ? state.activeId : ids[ids.length - 1] };
  }
  if (state?.results) return firstRunState(state.params || {}, state.results);
  return { runs: [], activeId: null };
}

/** Append a run, trimming the oldest beyond MAX_RUNS. */
export function addRun(runs, params, results) {
  const id = (runs.length ? Math.max(...runs.map((r) => r.id)) : 0) + 1;
  return { runs: [...runs, { id, params, results }].slice(-MAX_RUNS), activeId: id };
}
