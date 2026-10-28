from backend.services.tl_actions_tracker import _build_tracker_format_requests


def test_tracker_format_requests_preserve_order_and_skip_missing_banding_ids():
    requests = _build_tracker_format_requests(
        sheet_id=7,
        row_count=4,
        sheet_row_count=100,
        banded_ranges=[{"bandedRangeId": 10}, {}, {"bandedRangeId": 11}],
    )

    request_names = [next(iter(request)) for request in requests]
    assert request_names == (
        ["deleteBanding"] * 2
        + ["updateSheetProperties"]
        + ["updateDimensionProperties"] * 7
        + ["repeatCell"] * 8
        + ["addBanding"] * 2
        + ["setBasicFilter", "setDataValidation", "repeatCell", "autoResizeDimensions"]
    )
    assert [request["deleteBanding"]["bandedRangeId"] for request in requests[:2]] == [10, 11]
    assert requests[-1]["autoResizeDimensions"]["dimensions"] == {
        "sheetId": 7,
        "dimension": "ROWS",
        "startIndex": 1,
        "endIndex": 4,
    }


def test_tracker_format_requests_skip_row_resize_for_one_data_row():
    requests = _build_tracker_format_requests(
        sheet_id=3,
        row_count=1,
        sheet_row_count=20,
        banded_ranges=[],
    )

    assert next(iter(requests[-1])) == "repeatCell"
    assert not any("autoResizeDimensions" in request for request in requests)
