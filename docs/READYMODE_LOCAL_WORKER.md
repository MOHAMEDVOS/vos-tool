# ReadyMode local worker (first phase)

This optional worker runs **Scoring → Gather** requests from a trusted computer while VOS and its database stay on Railway. ReadyMode login and request code is reused unchanged. The worker opens outbound HTTPS requests to VOS; it does not expose a port on the computer.

## Start the worker

1. Deploy the backend and frontend changes to Railway. The database migration runs during backend startup.
2. Sign in to VOS as Owner. Open **Settings → System → App Config → ReadyMode Worker**.
3. Select **Railway** and save while preparing the worker. Click **Create worker token** and copy the token; it is shown only once.
4. On the computer that will run the worker, open a terminal in the project directory and activate the project's Python environment. Set the Railway backend's public base URL (without `/api`) and enter the token without putting it in shell history:

   ```zsh
   export VOS_API_URL="https://your-railway-backend.example"
   read -s "READYMODE_WORKER_TOKEN?Paste worker token: "
   echo
   export READYMODE_WORKER_TOKEN
   python -m automation.readymode_local_worker
   ```

5. Wait until the Owner settings page says the worker is connected. Then select **Local worker** and save. New Scoring → Gather requests will use it. Existing requests keep their selected route.

To turn local execution off, change the setting back to **Railway** and save. Then press **Ctrl+C** in the worker terminal and run `unset READYMODE_WORKER_TOKEN`. Rotating the worker token immediately invalidates the previous token.

## Data and scope

- The worker only handles the initial Scoring → Gather CSV operation in this phase.
- The VOS database temporarily holds queued parameters and the gathered result while Railway consumes it; the finished job row is then removed. No CSV, call rows, passwords, or ReadyMode cookies are written to the worker computer's disk or logs.
- Railway loads each user's saved ReadyMode credentials only when a job is claimed. The worker keeps them and the ReadyMode session in memory for that job.
- If the worker is offline, Scoring → Gather returns an error asking the user to start the worker or switch back to Railway.
- Do not paste the worker token into tickets, logs, or chat. Use **Rotate worker token** if it is exposed.

This does not move audit recording downloads, ReadyMode account creation/deletion, duplicate scans, or inactive-user scans. Those require later worker job types; until then, their existing Railway behavior is unchanged.
