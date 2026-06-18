/**
 * A2A response normalization.
 *
 * Canonical contract: JS consumers (agent card, queue consumers, manage_agents
 * callers) speak camelCase. Python A2A capabilities speak snake_case. This
 * module is the single place that bridges the two — Python values are never
 * expected to arrive camelCased, and JS consumers never need to know about the
 * snake_case originals (though we preserve them so callers that already adapted
 * to snake_case stay unbroken).
 *
 * Alias map (Python snake_case → JS camelCase):
 *   session_id   → sessionId
 *   run_id       → runId
 *   exit_status  → exitStatus
 *
 * Rules:
 *   - Each alias is additive: the original key is kept so legacy callers work.
 *   - Aliasing only happens when the camelCase key is NOT already present; an
 *     existing camelCase value is never clobbered.
 *   - A null/undefined input is returned as an empty object — callers own the
 *     fallback for required fields (e.g. `{ status: "completed" }`).
 *   - Any non-object input (including arrays/primitives/functions) is treated
 *     as malformed for this boundary and normalized to `{}`.
 */

/**
 * Explicit alias entries: each entry maps a Python snake_case field to its
 * canonical JS camelCase equivalent.
 *
 * Kept module-private to avoid accidental runtime mutation/coupling by external
 * consumers. Add new aliases here as needed.
 *
 * @type {ReadonlyArray<readonly [string, string]>}
 */
const ALIAS_MAP = Object.freeze([
  Object.freeze(['session_id', 'sessionId']),
  Object.freeze(['run_id', 'runId']),
  Object.freeze(['exit_status', 'exitStatus']),
])

/**
 * Normalize a raw Python A2A response object into the JS-canonical shape.
 *
 * JS camelCase keys are the authoritative contract for all queue consumers and
 * agent card readers. Python capabilities return snake_case; this function adds
 * the camelCase aliases without removing the originals (so callers that already
 * read snake_case keys continue to work).
 *
 * Non-object values are intentionally coerced to `{}` at this normalization
 * boundary to keep downstream consumers on a stable object contract.
 *
 * @param {unknown} raw - The artifact value parsed from the Python A2A
 *   JSON-RPC response.
 * @returns {Record<string, any>} A new object with all original fields plus
 *   camelCase aliases for any recognized snake_case fields.
 */
function normalizeA2AResponse(raw) {
  if (raw == null || typeof raw !== 'object' || Array.isArray(raw)) {
    return {}
  }

  const result = { ...raw }

  for (const [snakeKey, camelKey] of ALIAS_MAP) {
    // Additive aliasing only; never overwrite an explicitly provided camelCase value.
    if (Object.hasOwn(result, snakeKey) && !Object.hasOwn(result, camelKey)) {
      result[camelKey] = result[snakeKey]
    }
  }

  return result
}

module.exports = { normalizeA2AResponse }
