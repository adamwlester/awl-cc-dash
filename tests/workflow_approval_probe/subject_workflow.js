// Subject workflow for the workflow-APPROVAL-interception spike
// (tests/workflow_approval_probe/test_workflow_approval_intercept_live.py).
//
// This is the throwaway workflow whose APPROVAL GATE the spike intercepts. It is
// deliberately TINY - a single trivial agent - so that if the Approve path is
// exercised, at most one cheap subagent runs (~40-80k tokens) rather than a
// fan-out. The distinctive meta.name / meta.description / meta.phases below are
// exactly the "full preview" fields the interceptor must prove it can read out of
// the gate (from the hook's tool_input.script, and/or the on-screen dialog).
//
// The probe reads THIS FILE, strips these comment lines, and COLLAPSES the rest to
// a single line before asking a bridged Claude session to run it via the Workflow
// tool. Two rules make that safe and keep the file the single source of truth:
//   1. Every statement ends with an explicit semicolon, so collapsing newlines to
//      spaces stays valid JS.
//   2. No embedded newlines reach tmux send-keys (they would submit the prompt
//      early), and only plain ASCII / single-quoted strings are used.
// Keep meta.name === 'wf-approval-subject' (asserted by the probe).

export const meta = { name: 'wf-approval-subject', description: 'THROWAWAY subject for the awl-cc-dash approval-interception spike - one trivial agent that returns a constant word. Exists only so the dashboard can practice intercepting the workflow approval gate.', phases: [ { title: 'Solo', detail: 'one agent returns the single word intercepted' } ] };
phase('Solo');
const out = await agent('Reply with exactly this one word and nothing else, no punctuation: intercepted', { label: 'solo', phase: 'Solo' });
return { out };
