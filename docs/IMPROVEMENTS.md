# Improvements

This document was reset during the React cutover on the `NEW-UI` branch.

The current improvement backlog should target the active React + FastAPI stack:

- Expand browser smoke coverage for login, dashboard tabs, audit upload, call review audio, ReadyMode, phrase management, and settings.
- Add endpoint-level tests for phrase, quota, sharing, campaign report, and system routers.
- Add a React-aware Docker Hub publish script for `vos-backend` and `vos-webapp`.
- Move v2 authentication from localStorage JWTs to httpOnly cookies after the cutover is stable.
- Add CI jobs for `npx tsc -b --pretty false`, `npm run build`, backend import checks, and Docker image builds.

Historical recommendations for the retired Python UI are obsolete and should not guide new work.
