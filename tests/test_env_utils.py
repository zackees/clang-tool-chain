"""Tests for the env_utils module."""

import os
import unittest

from clang_tool_chain.env_utils import (
    CONTROLLABLE_FEATURES,
    get_disabled_features,
    is_auto_disabled,
    is_feature_disabled,
)


class TestEnvUtils(unittest.TestCase):
    """Test cases for environment variable utilities."""

    def setUp(self):
        """Save original environment variables."""
        self.original_env = os.environ.copy()

    def tearDown(self):
        """Restore original environment variables."""
        # Remove any test variables we added
        for key in list(os.environ.keys()):
            if key.startswith("CLANG_TOOL_CHAIN_NO_"):
                if key not in self.original_env:
                    del os.environ[key]
                else:
                    os.environ[key] = self.original_env[key]

    def test_is_auto_disabled_when_not_set(self):
        """Test that is_auto_disabled returns False when not set."""
        os.environ.pop("CLANG_TOOL_CHAIN_NO_AUTO", None)
        self.assertFalse(is_auto_disabled())

    def test_is_auto_disabled_when_set_to_1(self):
        """Test that is_auto_disabled returns True when set to '1'."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "1"
        self.assertTrue(is_auto_disabled())

    def test_is_auto_disabled_when_set_to_true(self):
        """Test that is_auto_disabled returns True when set to 'true'."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "true"
        self.assertTrue(is_auto_disabled())

    def test_is_auto_disabled_when_set_to_yes(self):
        """Test that is_auto_disabled returns True when set to 'yes'."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "yes"
        self.assertTrue(is_auto_disabled())

    def test_is_auto_disabled_when_set_to_0(self):
        """Test that is_auto_disabled returns False when set to '0'."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "0"
        self.assertFalse(is_auto_disabled())

    def test_is_feature_disabled_when_not_set(self):
        """Test that is_feature_disabled returns False when nothing is set."""
        os.environ.pop("CLANG_TOOL_CHAIN_NO_AUTO", None)
        os.environ.pop("CLANG_TOOL_CHAIN_NO_DIRECTIVES", None)
        self.assertFalse(is_feature_disabled("DIRECTIVES"))

    def test_is_feature_disabled_when_specific_var_set(self):
        """Test that is_feature_disabled returns True when specific var is set."""
        os.environ.pop("CLANG_TOOL_CHAIN_NO_AUTO", None)
        os.environ["CLANG_TOOL_CHAIN_NO_DIRECTIVES"] = "1"
        self.assertTrue(is_feature_disabled("DIRECTIVES"))

    def test_is_feature_disabled_when_auto_set(self):
        """Test that is_feature_disabled returns True when NO_AUTO is set."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "1"
        os.environ.pop("CLANG_TOOL_CHAIN_NO_DIRECTIVES", None)
        self.assertTrue(is_feature_disabled("DIRECTIVES"))

    def test_is_feature_disabled_all_features_via_auto(self):
        """Test that NO_AUTO disables all features."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "1"

        for feature in CONTROLLABLE_FEATURES:
            # Clear specific feature variable
            os.environ.pop(f"CLANG_TOOL_CHAIN_NO_{feature}", None)
            self.assertTrue(
                is_feature_disabled(feature),
                f"Feature {feature} should be disabled via NO_AUTO",
            )

    def test_get_disabled_features_when_none_disabled(self):
        """Test get_disabled_features returns empty list when nothing disabled."""
        os.environ.pop("CLANG_TOOL_CHAIN_NO_AUTO", None)
        for feature in CONTROLLABLE_FEATURES:
            os.environ.pop(f"CLANG_TOOL_CHAIN_NO_{feature}", None)

        self.assertEqual(get_disabled_features(), [])

    def test_get_disabled_features_when_auto_set(self):
        """Test get_disabled_features returns all features when NO_AUTO is set."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "1"

        disabled = get_disabled_features()
        self.assertEqual(set(disabled), set(CONTROLLABLE_FEATURES.keys()))

    def test_get_disabled_features_when_specific_set(self):
        """Test get_disabled_features returns specific features."""
        os.environ.pop("CLANG_TOOL_CHAIN_NO_AUTO", None)
        for feature in CONTROLLABLE_FEATURES:
            os.environ.pop(f"CLANG_TOOL_CHAIN_NO_{feature}", None)

        os.environ["CLANG_TOOL_CHAIN_NO_DIRECTIVES"] = "1"
        os.environ["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        disabled = get_disabled_features()
        self.assertIn("DIRECTIVES", disabled)
        self.assertIn("DEPLOY_LIBS", disabled)
        self.assertNotIn("SHARED_ASAN", disabled)

    def test_controllable_features_has_expected_features(self):
        """Test that CONTROLLABLE_FEATURES contains expected entries."""
        expected_features = [
            "DIRECTIVES",
            "SHARED_ASAN",
            "SANITIZER_ENV",
            "RPATH",
            "SYSROOT",
            "DEPLOY_LIBS",
            "DEPLOY_SHARED_LIB",
        ]

        for feature in expected_features:
            self.assertIn(
                feature,
                CONTROLLABLE_FEATURES,
                f"Expected feature {feature} in CONTROLLABLE_FEATURES",
            )

    def test_deploy_shared_lib_replaces_platform_specific(self):
        """Test that DEPLOY_SHARED_LIB exists and platform-specific ones don't."""
        # New cross-platform variable should exist
        self.assertIn("DEPLOY_SHARED_LIB", CONTROLLABLE_FEATURES)

        # Legacy platform-specific variables should NOT exist
        self.assertNotIn("DEPLOY_DLLS", CONTROLLABLE_FEATURES)
        self.assertNotIn("DEPLOY_DLLS_FOR_DLLS", CONTROLLABLE_FEATURES)
        self.assertNotIn("DEPLOY_SO", CONTROLLABLE_FEATURES)
        self.assertNotIn("DEPLOY_DYLIBS", CONTROLLABLE_FEATURES)

    def test_case_insensitive_truthy_values(self):
        """Test that truthy values are case insensitive."""
        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "TRUE"
        self.assertTrue(is_auto_disabled())

        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "True"
        self.assertTrue(is_auto_disabled())

        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "YES"
        self.assertTrue(is_auto_disabled())

        os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "Yes"
        self.assertTrue(is_auto_disabled())


if __name__ == "__main__":
    unittest.main()
