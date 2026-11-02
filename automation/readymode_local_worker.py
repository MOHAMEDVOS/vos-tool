"""Run ReadyMode jobs from a trusted local machine and return results to VOS."""

from __future__ import annotations

import ipaddress
import logging
import os
import time
from urllib.parse import urlsplit

import requests

from automation.readymode_http import ReadyModeHTTPClient, ReadyModeLoginError
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


class ReadymodeLocalWorker:
    def __init__(self, api_base_url: str, token: str):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _request(self, method: str, path: str, **kwargs):
        return self.session.request(
            method,
            f"{self.api_base_url}{path}",
            timeout=REQUEST_TIMEOUT,
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
        if job.get("job_type") != "scoring_gather":
            self._fail(job_id, claim_token, "unsupported_job_type")
            return

        try:
            result = self._gather_scoring(job, job_id, claim_token)
            self._request(
                "POST",
                f"/api/readymode-worker/jobs/{job_id}/complete",
                json={"claim_token": claim_token, "result": result},
            ).raise_for_status()
            logger.info("Completed local ReadyMode scoring gather job")
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("Could not return worker result to VOS (status=%s)", status_code)
        except Exception:
            logger.exception("Local ReadyMode scoring gather failed")
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
            url = str(dialer.get("url", ""))
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
