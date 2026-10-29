/**
 * The `provenance` object that both `meta.json` and `sample_funnel.json` carry (schema 0.2.0): which
 * parameters, code and upstream data versions produced the file. One validator, so the two files
 * cannot drift apart. Exactly these keys:
 *   params_hash    non-empty string, hash of the study parameters
 *   code_commit    non-empty string, git commit of the Python code
 *   sample_label   non-empty string, which sample the numbers describe
 *   dolt_commits   object with exactly `earnings` and `options`, each a non-empty string
 */
import { fail, isObject, isText, keyProblem, show, type Parsed } from './validate'

export interface Provenance {
  params_hash: string
  code_commit: string
  sample_label: string
  dolt_commits: { earnings: string; options: string }
}

const PROVENANCE_KEYS = ['params_hash', 'code_commit', 'sample_label', 'dolt_commits'] as const
const DOLT_COMMIT_KEYS = ['earnings', 'options'] as const

/** `where` is the path used in error messages, e.g. "provenance". */
export function parseProvenance(input: unknown, where = 'provenance'): Parsed<Provenance> {
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const top = keyProblem(where, input, PROVENANCE_KEYS)
  if (top) return fail(top)
  const { params_hash, code_commit, sample_label, dolt_commits } = input
  if (!isText(params_hash)) return fail(`${where}.params_hash must be a non-empty string, got ${show(params_hash)}`)
  if (!isText(code_commit)) return fail(`${where}.code_commit must be a non-empty string, got ${show(code_commit)}`)
  if (!isText(sample_label)) return fail(`${where}.sample_label must be a non-empty string, got ${show(sample_label)}`)

  if (!isObject(dolt_commits)) return fail(`${where}.dolt_commits must be an object, got ${show(dolt_commits)}`)
  const doltProblem = keyProblem(`${where}.dolt_commits`, dolt_commits, DOLT_COMMIT_KEYS)
  if (doltProblem) return fail(doltProblem)
  const { earnings, options } = dolt_commits
  if (!isText(earnings)) return fail(`${where}.dolt_commits.earnings must be a non-empty string, got ${show(earnings)}`)
  if (!isText(options)) return fail(`${where}.dolt_commits.options must be a non-empty string, got ${show(options)}`)

  return { ok: true, data: { params_hash, code_commit, sample_label, dolt_commits: { earnings, options } } }
}
