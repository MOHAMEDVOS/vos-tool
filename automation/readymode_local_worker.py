"""Run ReadyMode jobs from a trusted local machine and return results to VOS."""

from __future__ import annotations

import ipaddress
import base64
import io
import logging
import os
import json
import time
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

import requests

from automation.readymode_http import (
    DISPOSITION_TYPE_IDS,
    ReadyModeHTTPClient,
    ReadyModeLoginError,
    all_type_ids,
    resolve_agent_id,
    resolve_campaign_id,
)
from automation.download_readymode_calls import (
    UA,
    ReadyModeNoCallsError,
    _collect_tasks_for_dialer,
)
from automation.create_readymode_users import create_users_multi_dialer
from lib.scoring_sampler import parse_phone_agent_csv

logger = logging.getLogger("readymode_local_worker")
POLL_SECONDS = 3
REQUEST_TIMEOUT = (5, 30)


def _api_base_url() -> str:
    value = os.getenv("VOS_API_URL", "").strip().rstrip("/")
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("VOS_API_URL must be an absolute HTTPS URL")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("VOS_API_URL must be the backend base URL without a path")
    if parsed.scheme != "https":
        try:
            is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            is_loopback = parsed.hostname == "localhost"
        if not is_loopback:
            raise ValueError("VOS_API_URL must use HTTPS")
    return value


def _validate_readymode_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not hostname.endswith(".readymode.com")
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("ReadyMode dialers must use HTTPS on a readymode.com subdomain")
    return value


class ReadymodeLocalWorker:
    def __init__(self, api_base_url: str, token: str):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _request(self, method: str, path: str, **kwargs):
        timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
        session = kwargs.pop("session", self.session)
        return session.request(
            method,
            f"{self.api_base_url}{path}",
            timeout=timeout,
            **kwargs,
        )

    def run_forever(self) -> None:
        logger.info("ReadyMode local worker started; polling VOS for jobs")
        while True:
            try:
                response = self._request("POST", "/api/readymode-worker/jobs/claim")
                if response.status_code == 204:
                    time.sleep(POLL_SECONDS)
                    continue
                if response.status_code == 401:
                    logger.error("Worker token is invalid or has been rotated; create a new token")
                    return
                response.raise_for_status()
                job = response.json()
                self._run_job(job)
            except requests.RequestException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                logger.warning("VOS worker request failed (status=%s); will retry", status_code)
                time.sleep(POLL_SECONDS)
            except Exception:
                logger.exception("Worker could not process a job; continuing to poll")
                time.sleep(POLL_SECONDS)

    def _run_job(self, job: dict) -> None:
        job_id = str(job.get("job_id", ""))
        claim_token = str(job.get("claim_token", ""))
        if not job_id or not claim_token:
            logger.error("Received an invalid worker job")
            return
        job_type = job.get("job_type")
        handlers = {
            "scoring_gather": self._gather_scoring,
            "readymode_dialer_counts": self._find_busiest_dialer,
            "readymode_recordings": self._download_recordings,
            "readymode_create_users": self._create_readymode_users,
        }
        handler = handlers.get(job_type)
        if handler is None:
            self._fail(job_id, claim_token, "unsupported_job_type")
            return

        try:
            result = handler(job, job_id, claim_token)
            self._request(
                "POST",
                f"/api/readymode-worker/jobs/{job_id}/complete",
                json={"claim_token": claim_token, "result": result},
            ).raise_for_status()
            logger.info("Completed local ReadyMode %s job", job_type)
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("Local ReadyMode %s job HTTP request failed (status=%s)", job_type, status_code)
            self._fail(job_id, claim_token, "worker_request_failed")
        except Exception:
            logger.error("Local ReadyMode %s job failed", job_type)
            self._fail(job_id, claim_token, "worker_processing_failed")
        finally:
            job.clear()

    def _gather_scoring(self, job: dict, job_id: str, claim_token: str) -> dict:
        payload = job.get("payload") or {}
        rm_username = job.get("readymode_username")
        rm_password = job.get("readymode_password")
        if not rm_username or not rm_password:
            raise ValueError("ReadyMode credentials are unavailable")

        date = str(payload.get("date", ""))
        dispositions = payload.get("dispositions") or []
        dialers = payload.get("dialers") or []
        records_by_dialer = {}
        dialers_ok = []
        dialers_failed = []
        errors_by_dialer = {}

        for index, dialer in enumerate(dialers, start=1):
            name = str(dialer.get("name", ""))
            url = _validate_readymode_url(str(dialer.get("url", "")))
            self._progress(job_id, claim_token, f"Gathering {name} ({index}/{len(dialers)})")
            client = ReadyModeHTTPClient(url)
            try:
                client.login(rm_username, rm_password)
            except ReadyModeLoginError:
                dialers_failed.append(name)
                errors_by_dialer[name] = "readymode_login_failed"
                client.session.close()
                continue
            except Exception:
                dialers_failed.append(name)
                errors_by_dialer[name] = "readymode_login_failed"
                client.session.close()
                continue

            try:
                csv_bytes = client.export_call_log_csv(
                    time_from=_format_date(date),
                    time_to=_format_date(date),
                    dispositions=dispositions,
                )
                records = parse_phone_agent_csv(csv_bytes)
                records_by_dialer[name] = records
                dialers_ok.append(name)
            except Exception:
                dialers_failed.append(name)
                errors_by_dialer[name] = "readymode_export_failed"
            finally:
                client.session.close()

        return {
            "records_by_dialer": records_by_dialer,
            "dialers_ok": dialers_ok,
            "dialers_failed": dialers_failed,
            "errors_by_dialer": errors_by_dialer,
        }

    def _find_busiest_dialer(self, job: dict, job_id: str, claim_token: str) -> dict:
        payload = job.get("payload") or {}
        identifier = str(payload.get("identifier", "")).strip()
        task = payload.get("task")
        start_date = _format_date(str(payload.get("start_date", "")))
        end_date = _format_date(str(payload.get("end_date", "")))
        dialers = payload.get("dialers") or []
        rm_username = job.get("readymode_username")
        rm_password = job.get("readymode_password")
        if not identifier or task not in {"agent", "campaign"}:
            raise ValueError("Invalid dialer count request")

        self._progress(job_id, claim_token, f"Checking {len(dialers)} dialers")
        results = []
        failed = []
        with ThreadPoolExecutor(max_workers=max(1, len(dialers))) as pool:
            futures = {
                pool.submit(
                    _count_identifier_on_dialer,
                    task,
                    dialer,
                    rm_username,
                    rm_password,
                    identifier,
                    start_date,
                    end_date,
                ): dialer.get("name", "unknown")
                for dialer in dialers
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results.append(future.result())
                except Exception:
                    failed.append(name)

        found = [item for item in results if item["found"]]
        response = {
            "results": sorted(results, key=lambda item: item["count"], reverse=True),
            "busiest": max(found, key=lambda item: item["count"]) if found else None,
            "failed": failed,
        }
        response[f"{task}_name"] = identifier
        return response

    def _download_recordings(self, job: dict, job_id: str, claim_token: str) -> dict:
        payload = job.get("payload") or {}
        username = job.get("readymode_username")
        password = job.get("readymode_password")
        dialers = payload.get("dialers") or []
        if not username or not password or not dialers:
            raise ValueError("Invalid ReadyMode recording job")
        dialers = [
            {**dialer, "url": _validate_readymode_url(str(dialer.get("url", "")))}
            for dialer in dialers
        ]

        start_date = str(payload.get("start_date", ""))
        end_date = str(payload.get("end_date", ""))
        start_str = _format_date(start_date)
        if payload.get("start_time"):
            start_str = f"{start_str} {payload['start_time']}"
            date_only = "0"
        else:
            date_only = "1"
        end_str = _format_date(end_date)
        all_tasks = []
        skipped_count = 0
        dialers_failed = []
        track_recordings = bool(payload.get("track_recordings", True))

        def claim_records(dialer_host, recording_ids, _run_id, force_reaudit):
            if not track_recordings:
                return set(recording_ids)
            response = self._request(
                "POST",
                f"/api/readymode-worker/jobs/{job_id}/recordings/claim",
                json={
                    "claim_token": claim_token,
                    "dialer_host": dialer_host,
                    "recording_ids": recording_ids,
                    "force_reaudit": bool(force_reaudit),
                },
            )
            response.raise_for_status()
            return set(response.json().get("claimed_ids") or [])

        for index, dialer in enumerate(dialers, start=1):
            self._progress(job_id, claim_token, f"Collecting calls from {dialer['name']} ({index}/{len(dialers)})")
            output = io.StringIO()
            try:
                with redirect_stdout(output):
                    tasks, cookies, skipped = _collect_tasks_for_dialer(
                        str(dialer["url"]),
                        username,
                        password,
                        start_str,
                        end_str,
                        date_only,
                        payload.get("agent") or "All users",
                        payload.get("campaign_name") or None,
                        payload.get("disposition") or None,
                        int(payload.get("max_samples") or 50),
                        "",
                        registry_run_id=job_id,
                        force_reaudit=bool(payload.get("force_reaudit")),
                        claim_recordings_callback=claim_records,
                    )
            except ReadyModeNoCallsError:
                if index == 1:
                    return {"error_code": "readymode_no_calls", "records": [], "skipped_count": 0}
                dialers_failed.append(dialer["name"])
                continue
            except ReadyModeLoginError:
                if index == 1:
                    return {"error_code": "readymode_login_failed", "records": [], "skipped_count": 0}
                dialers_failed.append(dialer["name"])
                continue
            all_tasks.extend(
                (href, filename, cookies, identity, dialer, track_recordings)
                for href, _path, filename, identity in tasks
            )
            skipped_count += skipped

        if not all_tasks and not skipped_count:
            return {
                "error_code": "readymode_no_calls",
                "records": [],
                "skipped_count": 0,
                "dialers_failed": dialers_failed,
            }

        self._progress(job_id, claim_token, f"Downloading {len(all_tasks)} recordings")
        succeeded = []
        failed_claims = []
        with ThreadPoolExecutor(max_workers=min(5, max(1, len(all_tasks)))) as pool:
            futures = [
                pool.submit(
                    self._download_and_upload_recording,
                    job_id,
                    claim_token,
                    index,
                    len(all_tasks),
                    task,
                )
                for index, task in enumerate(all_tasks, start=1)
            ]
            for future in as_completed(futures):
                result = future.result()
                if result["accepted"]:
                    succeeded.append(result["record"])
                elif result.get("identity"):
                    failed_claims.append(result["identity"])

        if failed_claims and track_recordings:
            self._release_recording_claims(job_id, claim_token, failed_claims)
        return {
            "records": succeeded,
            "downloaded_count": len(succeeded),
            "skipped_count": skipped_count,
            "dialers_failed": dialers_failed,
        }

    def _download_and_upload_recording(
        self,
        job_id: str,
        claim_token: str,
        index: int,
        total: int,
        task: tuple,
    ) -> dict:
        href, filename, cookies, identity, dialer, track_recordings = task
        api_session = requests.Session()
        api_session.headers.update(self.session.headers)
        response = None
        try:
            self._request(
                "POST",
                f"/api/readymode-worker/jobs/{job_id}/progress",
                json={"claim_token": claim_token, "message": f"Downloading recording {index}/{total}"},
                session=api_session,
            ).raise_for_status()
            response = requests.get(
                href,
                cookies=cookies,
                headers={"User-Agent": UA},
                timeout=60,
                stream=True,
            )
            content_type = response.headers.get("Content-Type", "").lower()
            if response.status_code != 200 or "html" in content_type:
                return {"accepted": False, "identity": identity if track_recordings else None}

            upload = self._request(
                "PUT",
                f"/api/readymode-worker/jobs/{job_id}/recordings/upload",
                headers={
                    "X-Worker-Claim-Token": claim_token,
                    "X-Worker-Recording-Metadata": base64.urlsafe_b64encode(
                        json.dumps({
                            "filename": filename,
                            "dialer_name": dialer["name"],
                            "dialer_host": (identity or {}).get("dialer_host", ""),
                            "recording_id": (identity or {}).get("recording_id", ""),
                        }).encode("utf-8")
                    ).decode("ascii"),
                    "Content-Type": content_type or "application/octet-stream",
                },
                data=(chunk for chunk in response.iter_content(chunk_size=65536) if chunk),
                timeout=(10, 180),
                session=api_session,
            )
            upload.raise_for_status()
            result = upload.json()
            if not result.get("accepted"):
                return {"accepted": False, "identity": identity if track_recordings else None}
            return {
                "accepted": True,
                "record": {
                    "file_path": result["file_path"],
                    **((identity or {}) if track_recordings else {}),
                },
            }
        finally:
            if response is not None:
                response.close()
            api_session.close()

    def _release_recording_claims(self, job_id: str, claim_token: str, records: list[dict]) -> None:
        self._request(
            "POST",
            f"/api/readymode-worker/jobs/{job_id}/recordings/release",
            json={"claim_token": claim_token, "recordings": records},
        ).raise_for_status()

    def _create_readymode_users(self, job: dict, job_id: str, claim_token: str) -> dict:
        payload = job.get("payload") or {}
        secret_payload = job.get("secret_payload") or {}
        users = secret_payload.get("users") or []
        dialer_urls = [
            _validate_readymode_url(str(url))
            for url in payload.get("dialer_urls") or []
        ]
        if not users or not dialer_urls:
            raise ValueError("Invalid ReadyMode user-creation job")

        sensitive_values = [
            str(value)
            for user in users
            for value in (user.get("password"),)
            if value
        ]
        account_username = job.get("readymode_username")
        account_password = job.get("readymode_password")
        if account_username:
            sensitive_values.append(str(account_username))
        if account_password:
            sensitive_values.append(str(account_password))
        sensitive_values = sorted(set(sensitive_values), key=len, reverse=True)

        def safe_log(message: str) -> None:
            if any(
                marker in message.casefold()
                for marker in (
                    "set-cookie", "cookie:", "phpsessid", "__cf_bm", "stationid",
                    "csrf", "authorization", "bearer ",
                )
            ):
                message = "ReadyMode returned a sensitive response; details redacted"
            for value in sensitive_values:
                message = message.replace(value, "[redacted]")
            self._progress(job_id, claim_token, message[:255])

        results = create_users_multi_dialer(
            dialer_urls=dialer_urls,
            users=users,
            readymode_user=account_username,
            readymode_pass=account_password,
            log_callback=safe_log,
        )
        return {"results": _redact_secrets(results, sensitive_values)}

    def _progress(self, job_id: str, claim_token: str, message: str) -> None:
        self._request(
            "POST",
            f"/api/readymode-worker/jobs/{job_id}/progress",
            json={"claim_token": claim_token, "message": message},
        ).raise_for_status()

    def _fail(self, job_id: str, claim_token: str, error_code: str) -> None:
        try:
            self._request(
                "POST",
                f"/api/readymode-worker/jobs/{job_id}/fail",
                json={"claim_token": claim_token, "error_code": error_code},
            ).raise_for_status()
        except requests.RequestException:
            logger.warning("Could not report worker job failure to VOS")


def _format_date(value: str) -> str:
    from datetime import date

    return date.fromisoformat(value).strftime("%m/%d/%Y")


def _count_identifier_on_dialer(
    task: str,
    dialer: dict,
    username: str,
    password: str,
    identifier: str,
    start_date: str,
    end_date: str,
) -> dict:
    name = str(dialer.get("name", "unknown"))
    url = _validate_readymode_url(str(dialer.get("url", "")))
    client = ReadyModeHTTPClient(url)
    try:
        client.login(username, password)
        if task == "campaign":
            probe = client.fetch_report(time_from=start_date, time_to=end_date, page=0)
            record_id, _ = resolve_campaign_id(probe.get("campaignlist", {}), identifier)
            filters = {"restrict_campaign": record_id} if record_id else None
        else:
            dialer_map = client.init_call_log()
            types = all_type_ids(dialer_map or DISPOSITION_TYPE_IDS)
            probe = client.fetch_report(time_from=start_date, time_to=end_date, types=types, page=0)
            record_id, _ = resolve_agent_id(probe.get("userlist", {}), identifier)
            filters = {"restrict_uid": record_id, "types": types} if record_id else None

        if not record_id:
            return {"dialer": name, "url": url, "found": False, "count": 0}
        filtered = client.fetch_report(time_from=start_date, time_to=end_date, page=0, **filters)
        pages = int(filtered.get("pages") or 0)
        first_page_count = len(filtered.get("results") or {})
        if pages <= 1:
            count = first_page_count
        else:
            last = client.fetch_report(
                time_from=start_date,
                time_to=end_date,
                page=pages - 1,
                **filters,
            )
            count = (pages - 1) * 25 + len(last.get("results") or {})
        return {"dialer": name, "url": url, "found": True, "count": count}
    finally:
        client.session.close()


def _redact_secrets(value, secrets_to_redact):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if any(marker in key.casefold() for marker in ("password", "cookie", "token", "secret"))
            else _redact_secrets(item, secrets_to_redact)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item, secrets_to_redact) for item in value]
    if isinstance(value, str):
        if any(
            marker in value.casefold()
            for marker in (
                "set-cookie", "cookie:", "phpsessid", "__cf_bm", "stationid",
                "csrf", "authorization", "bearer ",
            )
        ):
            return "ReadyMode returned a sensitive response; details redacted"
        for secret in secrets_to_redact:
            value = value.replace(secret, "[redacted]")
    return value


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    token = os.getenv("READYMODE_WORKER_TOKEN", "").strip()
    if not token:
        raise SystemExit("READYMODE_WORKER_TOKEN is required")
    try:
        api_base_url = _api_base_url()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    ReadymodeLocalWorker(api_base_url, token).run_forever()


if __name__ == "__main__":
    main()
