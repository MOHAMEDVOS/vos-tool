# TL Actions form review and Podio confirmation

The **Send action** button opens the prefilled Podio and Google forms. Submit the Podio form yourself; VOS checks Podio automatically and changes the card to green when it finds the matching item. Submit the Google Form yourself as a separate step. If Podio already confirms an action, the card button opens only the Google Form.

The action card displays the original Actions sheet text, including its issue type, incident details, and row's Action Given value. The two forms use a separate custom report template: team leader, agent, fixed issue type **Late hours sheet/leave request submission**, the report sentence `Action of [Agent] was not sent by [Team Leader]`, action date, Reported by TL, and fixed `Action Given: 2$`. The team leader name in the report sentence matches the first line exactly; the source phone list and source Action Given value are omitted from the forms. The source issue type does not change the fixed issue type or Podio Incident dropdown choice. Google Form fields are prefilled from the reconciled action and lookup tabs, including the direct manager and team leader RES ID; the agent's RES ID is not used. Podio preselects the Agent relationship when there is one exact match, and pre-fills the auditor, team leader, incident details, fixed incident choice, and **$2** action. Google Action Applied is prefilled with **$2**. If the Agent cannot be matched uniquely, VOS still opens both forms with the Podio Agent blank and alerts you to select it manually. Review both forms and click Submit in each.

If the Agent cannot be matched uniquely, VOS still opens both forms with the Podio Agent blank and asks you to select it manually before submitting.

## Enable automatic Podio confirmation

1. In Podio API keys, create the VOS API key and set its return domain to `vos-tool.up.railway.app`.
2. Add `PODIO_CLIENT_ID`, `PODIO_CLIENT_SECRET`, and `PODIO_OAUTH_REDIRECT_URI=https://vos-tool.up.railway.app/api/tl-actions/podio/callback` to the **backend** Railway service. `PODIO_TL_ACTIONS_APP_ID` defaults to the TL Actions app ID (`2500783`). Keep `ENCRYPTION_KEY` stable so stored OAuth tokens can be decrypted.
3. Redeploy the backend, open TL Actions as the Owner, and click **Connect Podio** once. Approve the requested app read access.
4. After setup, clicking **Send action** saves a pending marker in this browser. VOS checks Podio every 15 seconds while the page is open, then stores a green confirmation when it finds the matching action.

The OAuth client secret and tokens must only be stored in Railway environment variables and the encrypted backend settings table. Never paste them into chat or commit them. If a secret has been exposed, revoke it in Podio and use a replacement.

The Google Form entry IDs are tied to the current form configuration. If its questions are removed and recreated, update `GOOGLE_FORM_ENTRIES` in `backend/services/tl_actions_submission.py`.
