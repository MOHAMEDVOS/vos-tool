# Plan: standardize TL Action forms

## Goal

Prepare both forms with a clear, plain-text action description. Every action uses **Late hours sheet/leave request submission** as its displayed issue type and as the Podio Incident dropdown choice, regardless of the source row's issue type.

## Chosen approach

Keep the source action's team leader, agent, date, and Reported by TL value. Replace the source incident/phone list with a concise report sentence using the agent and team leader names, and use a fixed Action Given value of `2$`. Format them as simple labeled lines like this:

```text
Team Leader: {team leader}
Agent Name: {agent}
Type of Issue: Late hours sheet/leave request submission
Details about incident:
Action of [{agent}] was not sent by [{team leader}]
{action date}
Reported by TL: {source value}
Action Given: 2$
```

This custom full text goes into the Podio incident details and Google Form description only. The TL Actions card continues to display the original source text, including the source issue type, incident details, and Action Given value. The person after “was not sent by” is the team leader exactly as shown in the first line. Strip HTML formatting such as `<br/>` from values before formatting and matching.

## Form fields

- Podio Incident dropdown: always select **Late hours sheet/leave request submission**.
- Podio Action: fixed **$2**.
- Google Action Applied: fixed **$2**.
- Template Action Given: fixed text **2$**, replacing the row's source value.
- Google Direct Manager: look up the action's team leader in the `TL ACM` tab.
- Google RES ID: look up the action's team leader in the `TL RES ID` tab. Do not use the agent's RES ID.
- Podio Agent relationship: match the action's agent name against the Podio form choices and preselect its item ID when there is one unique exact match. If there is no unique match, leave the field blank, open both forms anyway, and alert the user to select the Agent manually.
- Coaching and proof fields: leave blank.
- Open both forms for review; the user submits each manually.

## Missing-action filter

Ignore Actions sheet rows whose `Action Given` value is exactly `Verbal` before matching them with Payroll. Exclude those rows from both the visible missing results and the sheet action count; values such as `Verbal warning` remain eligible.

## Implementation steps

1. Use the fixed incident choice rather than mapping the source issue type to Podio choices.
2. Update the full-text formatter to use the fixed Type of Issue label, generate the report sentence, and include the action date and row values.
3. Keep the direct-manager and team-leader RES ID lookups, using the team leader written in the action itself.
4. Prefill the Podio Agent relationship from the form's available choices; fall back to a blank field and a clear warning without cancelling either form when it cannot match. Keep final review and submission manual.

## Verification plan

1. Prepare a sample action and confirm its text follows the format above, including the generated sentence, `Reported by TL`, `Action Given`, and the source date.
2. Confirm the Podio Incident choice is **Late hours sheet/leave request submission** for a row with a different source issue type too.
3. Confirm both form tabs open prefilled, including the Podio Agent when matched; verify an unmatched Agent only triggers a warning and the forms still open. Neither form is submitted automatically.

## Risks

The fixed category and generated report sentence intentionally replace each source row's issue label and phone list in the forms. Form field IDs and dropdown choices can change if either external form is edited. The Agent must appear exactly once in Podio's exposed form choices for automatic preselection.
