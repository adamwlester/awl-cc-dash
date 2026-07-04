// Subject workflow for the awl-cc-dash workflow-engine probe.
//
// This is NOT a product asset — it is the deterministic "thing to observe" that
// tests/workflow_probe/test_workflow_orchestration_live.py watches. A driver
// agent launches it with the Workflow tool:
//
//     Workflow({ scriptPath: "<repo>/tests/workflow_probe/subject_workflow.js" })
//
// then immediately runs the probe against the transcriptDir it returns. See
// tests/workflow_probe/RUNBOOK.md for the full protocol.
//
// It is designed to (a) exercise the whole script API the dashboard cares about
// — phase() / parallel() (barrier) / pipeline() (no barrier) / log() / a schema
// agent (structured output) — and (b) run long enough, with STAGGERED agent
// completions, that the probe can catch the run mid-flight and answer "is the
// run manifest written live or only at completion?". The `chain` phase asks for
// ~120-word prose then a rewrite, which stretches wall-clock to tens of seconds
// without needing Date/sleep (both unavailable in workflow scripts).

export const meta = {
  name: 'wf-probe-subject',
  description: 'Deterministic subject workflow for the awl-cc-dash workflow-engine probe — exercises phase/parallel/pipeline/log/schema and runs long enough (staggered, longer outputs) to be observed live.',
  phases: [
    { title: 'seed', detail: 'parallel — 3 short one-word agents (a barrier)' },
    { title: 'chain', detail: 'pipeline — 3 items x 2 stages, longer prose (staggered, no barrier)' },
    { title: 'typed', detail: 'one schema agent — validated structured output' },
  ],
}

// ── Phase 1: parallel() — a barrier over three quick agents. ────────────────
phase('seed')
const seeds = await parallel([
  () => agent('Name one primary color. Reply with one word only, no punctuation.', { label: 'seed:color', phase: 'seed' }),
  () => agent('Name one orchestral instrument. Reply with one word only, no punctuation.', { label: 'seed:instrument', phase: 'seed' }),
  () => agent('Name one planet in our solar system. Reply with one word only, no punctuation.', { label: 'seed:planet', phase: 'seed' }),
])
log(`seed done: ${seeds.filter(Boolean).length}/3 words`)

// ── Phase 2: pipeline() — each topic flows draft → tighten independently, ────
//    NO barrier between stages, so completions stagger across the run.
phase('chain')
const TOPICS = ['a quiet harbor at dawn', 'a crowded night market', 'a snowfield under stars']
const chained = await pipeline(
  TOPICS,
  // stage 1 — receives (prevResult, originalItem, index); for the first stage
  // prevResult === the item. Draft a ~120-word paragraph (long-ish on purpose).
  (topic, _item, i) =>
    agent(`Write a vivid ~120-word paragraph describing this scene: ${topic}. Prose only, no title, no preamble.`,
      { label: `draft#${i}`, phase: 'chain' }),
  // stage 2 — tighten the draft to three sentences.
  (draft, topic, i) =>
    agent(`Rewrite the following paragraph as exactly three crisp sentences, keeping the strongest imagery. Return only the three sentences.\n\nScene: ${topic}\n\nParagraph:\n${draft}`,
      { label: `tighten#${i}`, phase: 'chain' }),
)
log(`chain done: ${chained.filter(Boolean).length}/${TOPICS.length} scenes tightened`)

// ── Phase 3: a single agent with a JSON Schema — forces structured output. ──
phase('typed')
const SUMMARY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['headline', 'sceneCount', 'mood'],
  properties: {
    headline: { type: 'string', description: 'A short headline tying the scenes together.' },
    sceneCount: { type: 'integer', description: 'How many scenes were summarized.' },
    mood: { type: 'string', enum: ['calm', 'lively', 'tense', 'wistful'] },
  },
}
const scenes = chained.filter(Boolean)
const typed = await agent(
  `Summarize these ${scenes.length} tightened scenes into a single object per the schema.\n\n` +
    scenes.map((s, i) => `${i + 1}) ${s}`).join('\n\n'),
  { label: 'typed:summary', phase: 'typed', schema: SUMMARY_SCHEMA },
)

return { seeds, chained, typed }
