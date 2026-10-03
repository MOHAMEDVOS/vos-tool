# TL Actions reconciliation

The **TL Actions** page is available to Admin and Owner accounts. It compares rows in the `Actions` tab of the configured Google Sheet with Payroll actions in a selected `Created Date Range`.

## Backend configuration

Set these variables in the backend deployment environment:

- `PAYROLL_EMAIL` and `PAYROLL_PASSWORD`: dedicated Payroll account credentials. They are used only by the backend HTTP client and are never sent to the browser.
- `GOOGLE_SERVICE_ACCOUNT_JSON` (optional): the existing Google service-account configuration, used if the public CSV export is unavailable. Share the source spreadsheet with that service account if needed.
- `TL_ACTIONS_SPREADSHEET_ID` (optional): source spreadsheet ID. Defaults to the project Actions spreadsheet.

The backend signs in with `POST /login`, retains the returned bearer token in a temporary HTTP session, and fetches every page from `GET /action_againsts` using `created_start` and `created_end`. It does not use the browser or download the UI's current-page-only CSV.

## Result rules

The sheet is read from Google's public CSV export when its sharing setting permits link access; otherwise the backend can use its service account. The source sheet is filtered by its `Action Date` column. Payroll is filtered by its `Created Date Range`. The `Details` values are compared exactly after removing HTML markup/entities, normalizing Unicode compatibility forms, and collapsing whitespace. Text case, punctuation, numbers, and words remain significant. Duplicate details are matched one at a time.

- Only sheet actions without a remaining exact Payroll match are returned to the page. Exact matches and Payroll-only rows are omitted.
- Duplicate details are matched one at a time, so an extra repeated sheet action is still shown as missing.
- Rows whose `Action Given` value is exactly `Verbal` are ignored before reconciliation, so they do not appear in results or the sheet action count. This does not filter values such as `Verbal warning`.

Reconciliation is read-only. **Send action** prepares the selected missing row in the Podio webform and Google Form for review; it never submits either form. VOS preselects the Podio Agent when its list has one exact name match. If it cannot, both forms still open and VOS asks you to select the Agent manually. Review the details and press Submit in both forms. See [TL_ACTIONS_SUBMISSION_SETUP.md](TL_ACTIONS_SUBMISSION_SETUP.md).

## Team-leader tracking

After reconciliation, the tracking chart ranks team leaders by Actions-sheet rows missing from Payroll across the exact Start date and End date selected on the page. It does not split results into preset weeks or months. The date filter defaults to the last seven days and can be changed to any custom range. Verbal-only rows remain excluded.
