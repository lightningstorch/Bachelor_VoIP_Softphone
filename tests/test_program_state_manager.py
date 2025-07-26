import unittest

from utils.program_state_manager import ProgramStateManager


class TestProgramStateManager(unittest.TestCase):

    def setUp(self):
        ProgramStateManager._instance = None

    def tearDown(self):
        ProgramStateManager._instance = None

    def test_singleton_instance(self):
        """Test that ProgramStateManager is a singleton."""
        instance1 = ProgramStateManager()
        instance2 = ProgramStateManager()
        self.assertIs(instance1, instance2, "ProgramStateManager should be a singleton.")
        self.assertEqual(id(instance1), id(instance2), "Both instances should have the same ID.")

    def test_initial_mode(self):
        """Test that the initial mode is set to 'live' and source is None."""
        instance = ProgramStateManager()
        self.assertEqual(instance.get_mode(), "live", "Initial mode should be 'live'.")
        self.assertEqual(instance.get_source(), None, "Initial source should be None.")

    def test_get_set_mode(self):
        """Test setting the mode to 'file'."""
        instance = ProgramStateManager()
        instance.set_mode("file")
        self.assertEqual(instance.get_mode(), "file", "Mode should be set to 'file'.")

        with self.assertRaises(ValueError):
            instance.set_mode("invalid_mode")

    def test_get_set_source(self):
        """Test getting the current source."""
        instance = ProgramStateManager()
        instance.set_source("test_source")
        self.assertEqual(instance.get_source(), "test_source", "get_source should return 'test_source'.")

    def test_switch_mode(self):
        """Test switching modes and sources."""
        instance = ProgramStateManager()
        self.assertTrue(instance.switch_mode("file", "test_file.txt"), "Should switch to file mode with source 'test_file.txt'.")
        self.assertEqual(instance.get_mode(), "file", "Mode should be 'file'.")
        self.assertEqual(instance.get_source(), "test_file.txt", "Source should be 'test_file.txt'.")

        # Test switching to the same mode and source
        self.assertFalse(instance.switch_mode("file", "test_file.txt"), "Should not switch if already in the same mode and source.")

        # Test switching to a different mode
        self.assertTrue(instance.switch_mode("live", "test_interface"), "Should switch to live mode with source 'test_interface'.")
        self.assertEqual(instance.get_mode(), "live", "Mode should be 'live'.")
        self.assertEqual(instance.get_source(), "test_interface", "Source should be 'test_interface'.")
