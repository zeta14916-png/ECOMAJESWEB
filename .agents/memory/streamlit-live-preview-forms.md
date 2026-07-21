---
name: Streamlit live-preview computed fields
description: Why computed preview fields (e.g. a running total) must live outside st.form, and how to prefill a keyed widget on selection change.
---

# Streamlit live-preview computed fields

Inputs inside `st.form` do NOT trigger a rerun until the form is submitted, so any
computed/derived value shown inside the form (e.g. a live "total = a + b - c") stays
frozen until submit. e2e tests will flag this as a bug even though the value computed
on submit is correct.

**Rule:** if you want a computed field to update live as the user types, put the input
widgets OUTSIDE `st.form` and use a plain `st.button` to submit.

**Why:** forms batch state and only reconcile on submit; that is the whole point of a
form, but it defeats live previews.

**How to apply / gotchas:**
- Prefilling a keyed widget on a *selection change* (e.g. set salary field to the
  selected employee's base salary): do NOT pass `value=` to a keyed widget while also
  writing `st.session_state[key]` — Streamlit warns. Instead track the last selection
  in a separate key and, when it changes, write the new default into the widget's
  session_state key BEFORE the widget is created, and create the widget with `key=` only
  (no `value=`).
- To reset fields after a successful submit, `st.session_state.pop(key, None)` for each
  widget key (and the "last selection" tracker) then `st.rerun()`.
- number_input widgets that are never manually written to session_state can safely take
  `value=0.0` + `key=`; the warning only triggers when you set both `value=` and the
  session_state key yourself.
