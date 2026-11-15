---
name: gaptek-test
description: Usability-test a web flow as a simulated non-technical Indonesian user ("orang awam" / "gaptek", e.g. Bu Sri) using the gaptek MCP server, then propose code fixes. Use when the user says "test the <flow> as Bu Sri", "would my mom understand this checkout", "gaptek test", or asks for a non-technical-user usability check of a running web app.
---

# gaptek-test

Runs the `gaptek` MCP tools (`list_personas`, `run_test`, `get_findings`) against a **running**
local web app and turns the findings into code fixes.

## Hard rule: no developer context reaches the tester

The task you write is the only thing the simulated user receives besides the screen. It must read
like something the persona would say to themselves. Never put in `goal_for_persona`:
source code, file or component names, CSS selectors, button ids, URLs/routes, or words like
"click", "submit", "form", "field", "button". You may read the source code yourself to write fixes
afterwards — just never pass it into the task.

## Steps

1. **Find the flow and the app URL.** Ask the user only if you can't tell which flow they mean or
   where the dev server runs (check `package.json` scripts / README for the port). The app must be
   running; if it isn't, tell the user how to start it.
2. **Pick personas.** Call `list_personas`. Default to the one the user named, else `bu-sri`.
   For a sanity baseline also run `kontrol-melek-teknologi`: if the control fails too, the flow is
   broken (or the success criteria are wrong), not a usability problem.
3. **Write the task YAML** to `tasks/<flow-id>.yaml` (so it can be re-run):
   ```yaml
   id: checkout
   url: http://localhost:5173/
   goal_for_persona: >
     Kamu mau beli dua bungkus kopi, terus bayar pakai QRIS.
     Nomor HP-mu 081234567890. Kalau diminta kode dari SMS, kodenya 482913.
   success:
     url_contains: "/order/success"     # and/or
     text_visible: "Pesanan berhasil"
   progress_hints: ["/cart", "/payment"]
   max_steps: 40
   ```
   Goal in everyday Indonesian, in the persona's own words. Include any personal data the persona
   would know (phone number, name, address) and any code they'd receive by SMS/email.
   Success criteria must be something only reachable by finishing the flow.
4. **Run.** Call `run_test(persona, task="tasks/<flow-id>.yaml")`. It returns a `run_id`
   immediately. A run takes a few minutes; poll `get_findings(run_id)` every ~30 s until `status`
   is `done` or `error`. Several personas can run at once.
5. **Read findings.** `findings.issues` are ranked by severity, each with the step, screen,
   evidence screenshots and a suggestion. `report` is an HTML report path — give it to the user.
   If `analysis_error` is set, the run finished but wasn't analyzed (usually a missing API key);
   say so.
6. **Propose fixes.** Map each high/medium issue to the code that renders that screen and propose
   a concrete change (usually wording: replace jargon/English with plain Indonesian; add visible
   text labels to icon-only buttons; make tiny text bigger). Quote the suggested UI text.
   Apply edits only if the user asks.

## Always say

Results are a **simulation**: hypotheses to confirm with real users, not user research.
