"""Preferences Service — per-user settings and customization.

Each user can override the system defaults with their own preferences.
Preferences are stored in the user record (SQLite) and merged on top of
the global config at request time.
"""
from __future__ import annotations

import copy
from typing import Any

from screener.core.config import AppConfig, config
from screener.core.responses import ErrorCodes, ValidationError
from screener.core.user_models import UserStore, user_store


class PreferencesService:
    """Manages per-user preferences, overlaying them on the global config."""

    def __init__(self, store: UserStore | None = None):
        self._store = store or user_store

    # ------------------------------------------------------------------ #
    # Get preferences
    # ------------------------------------------------------------------ #

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        """Get a user's stored preferences (raw dict)."""
        return self._store.get_preferences(user_id)

    def get_merged_config(self, user_id: str) -> dict[str, Any]:
        """Get the user's effective config = system defaults + user overrides.

        Returns a dict in the same shape as `config.editable_snapshot()`.
        """
        defaults = config.editable_snapshot()
        user_prefs = self.get_preferences(user_id)
        return self._deep_merge(defaults, user_prefs)

    def get_effective_config(self, user_id: str) -> AppConfig:
        """Get an AppConfig instance with user overrides applied.

        This creates a temporary config clone — does NOT modify the global.
        """
        user_prefs = self.get_preferences(user_id)
        if not user_prefs:
            return config

        # Create a shallow copy of config and apply user prefs
        effective = copy.copy(config)
        for section in config._SECTIONS:
            if section in user_prefs:
                model = type(getattr(config, section))
                current = getattr(config, section).model_dump()
                current.update(user_prefs[section])
                setattr(effective, section, model(**current))
        if "default_universe" in user_prefs:
            effective.default_universe = [
                str(s).strip().upper()
                for s in user_prefs["default_universe"]
                if str(s).strip()
            ]
        return effective

    # ------------------------------------------------------------------ #
    # Update preferences
    # ------------------------------------------------------------------ #

    def update_preferences(self, user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Apply a partial preferences patch for a user.

        Validates against the same rules as the global config.
        Returns the merged (effective) config after applying.
        """
        if not isinstance(patch, dict) or not patch:
            raise ValidationError("Empty preferences payload")

        allowed = config.editable_snapshot()
        unknown = [k for k in patch if k not in allowed]
        if unknown:
            raise ValidationError(
                f"Unknown preference key(s): {', '.join(sorted(unknown))}",
                details={"unknown_keys": sorted(unknown), "allowed_keys": sorted(allowed)},
            )

        for section, value in patch.items():
            if isinstance(allowed.get(section), dict):
                if not isinstance(value, dict):
                    raise ValidationError(
                        f"Preference section '{section}' must be an object",
                        details={"section": section},
                    )
                unknown_fields = [key for key in value if key not in allowed[section]]
                if unknown_fields:
                    raise ValidationError(
                        f"Unknown field(s) in '{section}': {', '.join(sorted(unknown_fields))}",
                        details={
                            "section": section,
                            "unknown_keys": sorted(unknown_fields),
                            "allowed_keys": sorted(allowed[section]),
                        },
                    )

        if "default_universe" in patch:
            universe = patch["default_universe"]
            if not isinstance(universe, list):
                raise ValidationError("Preference 'default_universe' must be a list")
            patch = copy.deepcopy(patch)
            patch["default_universe"] = self._normalize_symbols(universe)

        # Get current prefs and merge
        current = self.get_preferences(user_id)
        merged_patch = self._deep_merge(current, patch)

        # Validate by attempting to build the sub-configs
        effective = self._deep_merge(allowed, merged_patch)
        for section in config._SECTIONS:
            if section in merged_patch:
                model = type(getattr(config, section))
                try:
                    model(**effective[section])
                except Exception as e:
                    raise ValidationError(
                        f"Invalid value in '{section}': {e}",
                        details={"section": section, "error": str(e)},
                    )

        # Persist
        self._store.update_preferences(user_id, merged_patch)
        return self.get_merged_config(user_id)

    def reset_preferences(self, user_id: str) -> dict[str, Any]:
        """Reset a user's preferences to system defaults."""
        self._store.update_preferences(user_id, {})
        return self.get_merged_config(user_id)

    # ------------------------------------------------------------------ #
    # Watchlist helpers
    # ------------------------------------------------------------------ #

    def get_watchlist(self, user_id: str) -> list[str]:
        """Get the user's personal watchlist (stored in preferences)."""
        prefs = self.get_preferences(user_id)
        return prefs.get("watchlist", config.default_universe)

    def set_watchlist(self, user_id: str, symbols: list[str]) -> list[str]:
        """Set the user's personal watchlist."""
        cleaned = self._normalize_symbols(symbols)
        current = self.get_preferences(user_id)
        current["watchlist"] = cleaned
        self._store.update_preferences(user_id, current)
        return cleaned

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override into base (returns a new dict)."""
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = PreferencesService._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    @staticmethod
    def _normalize_symbols(symbols: list[Any]) -> list[str]:
        """Normalize and de-duplicate symbols while preserving their order."""
        normalized: list[str] = []
        seen: set[str] = set()
        for value in symbols:
            symbol = str(value).strip().upper()
            if symbol and symbol not in seen:
                normalized.append(symbol)
                seen.add(symbol)
        return normalized
