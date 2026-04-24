from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd


class AsterixFilters:
    """Keeps a temporary filtered DataFrame derived from an immutable base DataFrame."""

    NOT_IDENTIFIED_TOKEN = "__NOT_IDENTIFIED__"
    TYP_020_DISCARD = {
        "No detection",
        "PSR",
        "SSR",
        "SSR + PSR",
    }
    _TIME_VALUE_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?(?::\d{1,3})?$")

    def __init__(self) -> None:
        self._base_df = pd.DataFrame()
        self._filtered_df = pd.DataFrame()
        self._active_filters: dict[str, Any] = {}

    def set_base_dataframe(self, df: pd.DataFrame) -> None:
        self._base_df = df.reset_index(drop=True)
        self._filtered_df = self._base_df
        self._active_filters = {}

    def clear(self) -> None:
        self._base_df = pd.DataFrame()
        self._filtered_df = pd.DataFrame()
        self._active_filters = {}

    def get_base_dataframe(self) -> pd.DataFrame:
        return self._base_df

    def get_filtered_dataframe(self) -> pd.DataFrame:
        return self._filtered_df

    def get_active_filters(self) -> dict[str, Any]:
        return dict(self._active_filters)

    def apply_filters(self, **filters: Any) -> pd.DataFrame:
        cleaned = self._clean_filters(filters)
        self._active_filters = cleaned
        self._filtered_df = self._compute_filtered_dataframe(self._base_df, **cleaned)
        return self._filtered_df

    def get_category_filter_options(self) -> list[str]:
        # Requested by product: fixed multi-select options CAT021 and CAT048.
        return ["CAT021", "CAT048"]

    def get_target_identification_filter(self) -> dict[str, Any]:
        id_col = self._col_from(self._base_df, "TARGET_IDENTIFICATION", "callsign")
        sqk_col = self._col_from(self._base_df, "MODE_3/A", "squawk")
        if id_col is None:
            return {
                "groups": [],
                "all_values": [],
            }

        grouped: dict[str, set[str]] = {}
        flat_targets: list[str] = []
        flat_target_set: set[str] = set()
        member_rows: dict[str, int] = {}
        fix_transponder: set[str] = set()
        fix_member_rows: dict[str, int] = {}
        not_identified_count = 0

        for idx, raw_id in self._base_df[id_col].items():
            normalized_id = self._normalize_target_identification(raw_id)
            raw_sqk = self._base_df.at[idx, sqk_col] if sqk_col else None
            is_fix_transponder = self._is_fix_transponder(raw_sqk) or self._is_fix_transponder_target_identification(normalized_id)

            if is_fix_transponder:
                if normalized_id is not None:
                    fix_transponder.add(normalized_id)
                    fix_member_rows[normalized_id] = fix_member_rows.get(normalized_id, 0) + 1
                continue

            if normalized_id is None:
                not_identified_count += 1
                continue

            member_rows[normalized_id] = member_rows.get(normalized_id, 0) + 1

            # Group only if the first 3 chars are alphabetic and the suffix has at least one digit.
            prefix = normalized_id[:3] if len(normalized_id) >= 3 else normalized_id
            suffix = normalized_id[3:]
            is_groupable = prefix.isalpha() and any(ch.isdigit() for ch in suffix)

            if is_groupable:
                grouped.setdefault(prefix, set()).add(normalized_id)
            elif normalized_id not in flat_target_set:
                flat_target_set.add(normalized_id)
                flat_targets.append(normalized_id)

        groups: list[dict[str, Any]] = []
        for prefix in sorted(grouped.keys()):
            members = sorted(grouped[prefix])
            groups.append({
                "group_id": prefix,
                "group_label": prefix,
                "display_mode": "group",
                "members": members,
                "member_count": len(members),
                "member_rows": {member: member_rows.get(member, 0) for member in members},
            })

        if flat_targets:
            groups.append({
                "group_id": "TARGET_IDENTIFICATION_FLAT",
                "group_label": "",
                "display_mode": "flat",
                "members": flat_targets,
                "member_count": len(flat_targets),
                "member_rows": {member: member_rows.get(member, 0) for member in flat_targets},
            })

        if not_identified_count > 0:
            groups.append({
                "group_id": "NOT_IDENTIFIED",
                "group_label": "",
                "display_mode": "flat",
                "members": [self.NOT_IDENTIFIED_TOKEN],
                "member_count": 1,
                "member_rows": {self.NOT_IDENTIFIED_TOKEN: not_identified_count},
            })

        if fix_transponder:
            groups.append({
                "group_id": "INDEPENDIENTES",
                "group_label": "Independientes",
                "members": sorted(fix_transponder),
                "member_count": len(fix_transponder),
                "member_rows": {member: fix_member_rows.get(member, 0) for member in sorted(fix_transponder)},
            })

        grouped_values = {m for members in grouped.values() for m in members}
        all_values = sorted(grouped_values)
        all_values.extend(flat_targets)
        if not_identified_count > 0:
            all_values.append(self.NOT_IDENTIFIED_TOKEN)
        all_values.extend(sorted(fix_transponder))
        dedup_all_values = list(dict.fromkeys(all_values))

        return {
            "groups": groups,
            "all_values": dedup_all_values,
        }

    def _compute_filtered_dataframe(self, df: pd.DataFrame, **filters: Any) -> pd.DataFrame:
        if df.empty:
            return df

        filtered = df

        id_col = self._col_from(filtered, "TARGET_IDENTIFICATION", "callsign")
        target_identifications = filters.get("target_identifications")
        if target_identifications is not None and id_col:
            if isinstance(target_identifications, list) and not target_identifications:
                return filtered.iloc[0:0].reset_index(drop=True)

            selected = {
                normalized
                for normalized in (
                    self._normalize_target_identification(value)
                    for value in target_identifications
                )
                if normalized is not None
            }
            if selected:
                current_ids = filtered[id_col].map(self._normalize_target_identification)
                include_not_identified = self.NOT_IDENTIFIED_TOKEN in selected
                selected.discard(self.NOT_IDENTIFIED_TOKEN)

                match_mask = current_ids.isin(selected)
                if include_not_identified:
                    match_mask = match_mask | current_ids.isna()

                filtered = filtered[match_mask]

        callsigns = filters.get("callsigns")
        if callsigns and id_col:
            selected_callsigns = {
                normalized
                for normalized in (
                    self._normalize_target_identification(value)
                    for value in callsigns
                )
                if normalized is not None
            }
            if selected_callsigns:
                current_ids = filtered[id_col].map(self._normalize_target_identification)
                filtered = filtered[current_ids.isin(selected_callsigns)]

        cat_col = self._col_from(filtered, "CAT", "category")
        categories = filters.get("categories")
        if categories is not None and cat_col:
            if isinstance(categories, list) and not categories:
                return filtered.iloc[0:0].reset_index(drop=True)

            selected_categories = {
                normalized
                for normalized in (
                    self._normalize_category(value)
                    for value in categories
                )
                if normalized is not None
            }
            if selected_categories:
                current_categories = filtered[cat_col].map(self._normalize_category)
                filtered = filtered[current_categories.isin(selected_categories)]

        sqk_col = self._col_from(filtered, "MODE_3/A", "squawk")
        squawks = filters.get("squawks")
        if squawks and sqk_col:
            filtered = filtered[filtered[sqk_col].astype(str).isin(squawks)]

        alt_col = self._col_from(filtered, "FL", "altitude_ft")
        altitude_min = filters.get("fl_min", filters.get("altitude_min"))
        altitude_max = filters.get("fl_max", filters.get("altitude_max"))
        keep_fl_null = filters.get("fl_keep_null", True)
        if alt_col:
            altitude_series = pd.to_numeric(filtered[alt_col], errors="coerce")
            has_range_filter = altitude_min is not None or altitude_max is not None

            if has_range_filter:
                range_mask = pd.Series(True, index=filtered.index)
                if altitude_min is not None:
                    range_mask = range_mask & (altitude_series >= float(altitude_min))
                if altitude_max is not None:
                    range_mask = range_mask & (altitude_series <= float(altitude_max))

                if keep_fl_null:
                    range_mask = range_mask | altitude_series.isna()

                filtered = filtered[range_mask]
                altitude_series = pd.to_numeric(filtered[alt_col], errors="coerce")

            if keep_fl_null is False:
                filtered = filtered[altitude_series.notna()]
                altitude_series = pd.to_numeric(filtered[alt_col], errors="coerce")

        on_ground = filters.get("on_ground")
        if on_ground is False:
            # Product rule: unchecked ON GROUND removes rows with H(m) <= 0.
            h_col = self._col_from(filtered, "H(m)", "H_M")
            if h_col:
                h_series = pd.to_numeric(filtered[h_col], errors="coerce")
                filtered = filtered[h_series.isna() | (h_series > 0)]

        pure_white = filters.get("pure_white")
        if pure_white is True:
            typ_col = self._col_from(filtered, "TYP_020")
            if typ_col:
                keep_typ = ~filtered[typ_col].isin(self.TYP_020_DISCARD)
                filtered = filtered[keep_typ]

        time_col = self._col_from(filtered, "TIME", "timestamp")
        time_start = self._parse_time_filter_value(filters.get("time_start"))
        time_end = self._parse_time_filter_value(filters.get("time_end"))
        if time_col and (time_start is not None or time_end is not None):
            time_series = pd.to_numeric(
                filtered[time_col].map(self._parse_time_filter_value),
                errors="coerce",
            )
            if time_start is not None and time_series.notna().any():
                filtered = filtered[time_series >= float(time_start)]
                time_series = pd.to_numeric(
                    filtered[time_col].map(self._parse_time_filter_value),
                    errors="coerce",
                )
            if time_end is not None and time_series.notna().any():
                filtered = filtered[time_series <= float(time_end)]

        return filtered.reset_index(drop=True)

    @staticmethod
    def _is_fix_transponder(value: Any) -> bool:
        if value is None:
            return False

        try:
            if pd.isna(value):
                return False
        except Exception:
            pass

        text = str(value).strip()
        if not text:
            return False

        return text == "7777"

    @staticmethod
    def _is_fix_transponder_target_identification(value: Any) -> bool:
        if value is None:
            return False

        text = str(value).strip().upper()
        if not text:
            return False

        return text.startswith("7777")

    @staticmethod
    def _col_from(df: pd.DataFrame, *candidates: str) -> str | None:
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    @staticmethod
    def _normalize_category(value: Any) -> str | None:
        if pd.isna(value):
            return None

        text = str(value).strip().upper()
        if not text:
            return None

        if text.startswith("CAT"):
            suffix = text[3:]
            if suffix.isdigit():
                return f"CAT{int(suffix):03d}"
            return text

        if text.isdigit():
            return f"CAT{int(text):03d}"

        return text

    @staticmethod
    def _normalize_target_identification(value: Any) -> str | None:
        if value is None:
            return None

        try:
            if pd.isna(value):
                return None
        except Exception:
            # Some object types do not support scalar NA checks.
            pass

        text = str(value).strip().upper()
        if not text:
            return None

        # Drop common pseudo-empty markers after string conversion.
        if text in {"NAN", "NONE", "NULL", "N/A", "NA", "<NA>"}:
            return None

        # Normalize internal whitespace to avoid duplicated logical IDs.
        text = re.sub(r"\s+", "", text)
        return text or None

    @staticmethod
    def _parse_time_filter_value(value: Any) -> float | None:
        if value is None:
            return None

        try:
            if pd.isna(value):
                return None
        except Exception:
            pass

        if isinstance(value, (int, float)):
            return float(math.ceil(value))

        text = str(value).strip()
        if not text:
            return None

        m = AsterixFilters._TIME_VALUE_RE.match(text)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2))
            second = int(m.group(3) or 0)
            if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                # Ignore milliseconds by design.
                return float(hour * 3600 + minute * 60 + second)

        try:
            numeric = float(text)
            return float(math.ceil(numeric))
        except ValueError:
            pass

        parsed = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None

        timestamp = float(parsed.timestamp())
        return float(math.ceil(timestamp))

    def _clean_filters(self, filters: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in filters.items():
            if value is None:
                continue
            if isinstance(value, list) and not value:
                if key in {"categories", "target_identifications"}:
                    cleaned[key] = value
                continue
            cleaned[key] = value
        return cleaned
