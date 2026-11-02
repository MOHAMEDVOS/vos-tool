# ReadyMode local worker

This optional worker runs ReadyMode HTTP requests from a trusted computer while VOS, its database, call analysis, and stored recordings stay on Railway. The existing ReadyMode login code is reused. The worker opens outbound HTTPS requests to VOS; it does not expose a port on the computer.

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

5. Wait until the Owner settings page says the worker is connected. Then select **Local worker** and save. New Scoring Gather/Audit, ReadyMode audits, Find busiest dialer, and ReadyMode user-creation requests will use it. Existing requests keep their selected route.

To turn local execution off, change the setting back to **Railway** and save. Then press **Ctrl+C** in the worker terminal and run `unset READYMODE_WORKER_TOKEN`. Rotating the worker token immediately invalidates the previous token.

## Data and scope

- Railway temporarily holds queued parameters and job results, then removes the finished job. User-creation passwords are encrypted in a separate short-lived secret row and deleted when the job finishes or expires.
- Railway loads the requesting user's saved ReadyMode credentials when a job is claimed. The worker keeps credentials and ReadyMode session cookies in memory for that job; it does not log them or write them to disk.
- Audit audio is streamed through the worker in chunks and written directly to Railway's configured recordings storage. Audio is not saved on the worker computer. Railway runs the existing analysis and saves VOS audit records as usual.
- If the worker is offline, these requests return an error asking the user to start the worker or switch back to Railway.
- Do not paste the worker token into tickets, logs, or chat. Use **Rotate worker token** if it is exposed.

ReadyMode user deletion, duplicate scans, and inactive-user scans continue to use Railway.
