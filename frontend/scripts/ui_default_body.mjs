// ui_default_body.mjs — print the /api/design body the web UI sends at its defaults.
//
// Built with the frontend's own DEFAULTS and buildDesignBody (utils/designRequest.js),
// so backend/scripts/ui_default_check.py designs with exactly what the form sends.
// The sequence group is left for the caller to fill in.
//
// Usage (repo root): node frontend/scripts/ui_default_body.mjs
import { DEFAULTS } from '../src/constants/defaults.js';
import { buildDesignBody } from '../src/utils/designRequest.js';

const form = {
  sequence: { ...DEFAULTS.sequence },
  thermodynamic: { ...DEFAULTS.thermodynamic },
  primerConstraints: { ...DEFAULTS.primerConstraints },
  qpcr: { ...DEFAULTS.qpcr },
  detectionMethod: { ...DEFAULTS.detectionMethod },
  experimentalContext: { ...DEFAULTS.experimentalContext },
};
process.stdout.write(JSON.stringify(buildDesignBody(form)));
