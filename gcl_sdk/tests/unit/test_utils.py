#    Copyright 2025 Genesis Corporation.
#
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import tempfile
import unittest
from unittest import mock

from gcl_sdk.common import utils


class TestSwapDirs(unittest.TestCase):
    """Test cases for swap_dirs function."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.dir1 = os.path.join(self.test_dir, "dir1")
        self.dir2 = os.path.join(self.test_dir, "dir2")

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_swap_both_dirs_exist_same_parent(self):
        """Test swapping two existing directories in same parent."""
        # Create directories with test files
        os.makedirs(self.dir1)
        os.makedirs(self.dir2)

        with open(os.path.join(self.dir1, "file1.txt"), "w") as f:
            f.write("content1")
        with open(os.path.join(self.dir2, "file2.txt"), "w") as f:
            f.write("content2")

        # Swap directories
        utils.swap_dirs(self.dir1, self.dir2)

        # Verify swap occurred
        self.assertTrue(os.path.exists(self.dir1))
        self.assertTrue(os.path.exists(self.dir2))
        self.assertTrue(os.path.exists(os.path.join(self.dir1, "file2.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dir2, "file1.txt")))

        with open(os.path.join(self.dir1, "file2.txt"), "r") as f:
            self.assertEqual(f.read(), "content2")
        with open(os.path.join(self.dir2, "file1.txt"), "r") as f:
            self.assertEqual(f.read(), "content1")

    def test_swap_one_dir_exists(self):
        """Test swapping when only one directory exists."""
        # Create only dir1
        os.makedirs(self.dir1)
        with open(os.path.join(self.dir1, "file1.txt"), "w") as f:
            f.write("content1")

        # Force macOS path since renameat2 requires both dirs to exist
        with mock.patch("gcl_sdk.common.utils.renameat2", None):
            utils.swap_dirs(self.dir1, self.dir2)

        # Verify dir1 moved to dir2
        self.assertFalse(os.path.exists(self.dir1))
        self.assertTrue(os.path.exists(self.dir2))
        self.assertTrue(os.path.exists(os.path.join(self.dir2, "file1.txt")))

        with open(os.path.join(self.dir2, "file1.txt"), "r") as f:
            self.assertEqual(f.read(), "content1")

    def test_swap_both_dirs_dont_exist(self):
        """Test swapping when both directories don't exist."""
        # Force macOS path since renameat2 requires both dirs to exist
        with mock.patch("gcl_sdk.common.utils.renameat2", None):
            utils.swap_dirs(self.dir1, self.dir2)

        # Both should still not exist
        self.assertFalse(os.path.exists(self.dir1))
        self.assertFalse(os.path.exists(self.dir2))

    def test_swap_file_raises_error(self):
        """Test that swapping with a file raises ValueError."""
        # Create dir1 as a directory and dir2 as a file
        os.makedirs(self.dir1)
        with open(self.dir2, "w") as f:
            f.write("I'm a file")

        # Force macOS path to get the file validation check
        with mock.patch("gcl_sdk.common.utils.renameat2", None):
            with self.assertRaises(ValueError) as cm:
                utils.swap_dirs(self.dir1, self.dir2)
            self.assertIn("exists but is not a directory", str(cm.exception))

    def test_swap_dirs_different_parents_raises_error(self):
        """Test that swapping directories in different parents raises error for macOS path."""
        # Create directories in different parents
        dir1_parent = os.path.join(self.test_dir, "parent1")
        dir2_parent = os.path.join(self.test_dir, "parent2")
        os.makedirs(dir1_parent)
        os.makedirs(dir2_parent)

        dir1_alt = os.path.join(dir1_parent, "dir1")
        dir2_alt = os.path.join(dir2_parent, "dir2")
        os.makedirs(dir1_alt)
        os.makedirs(dir2_alt)

        # Mock renameat2 to be None to force macOS path
        with mock.patch("gcl_sdk.common.utils.renameat2", None):
            with self.assertRaises(ValueError) as cm:
                utils.swap_dirs(dir1_alt, dir2_alt)
            self.assertIn("same parent directory", str(cm.exception))

    @mock.patch("gcl_sdk.common.utils.renameat2")
    def test_swap_linux_path(self, mock_renameat2):
        """Test Linux path using renameat2."""
        # Create directories
        os.makedirs(self.dir1)
        os.makedirs(self.dir2)

        # Mock renameat2 to be available
        mock_exchange = mock.Mock()
        mock_renameat2.exchange = mock_exchange

        # Mock renameat2 import to be truthy
        with mock.patch("gcl_sdk.common.utils.renameat2", mock_renameat2):
            utils.swap_dirs(self.dir1, self.dir2)

        # Verify renameat2.exchange was called
        mock_exchange.assert_called_once_with(self.dir1, self.dir2)

    def test_mac_compatible_swap_subdirectories(self):
        """Test macOS-compatible swap with subdirectories."""
        # Create directories with subdirectories
        os.makedirs(self.dir1)
        os.makedirs(self.dir2)
        os.makedirs(os.path.join(self.dir1, "subdir"))
        os.makedirs(os.path.join(self.dir2, "subdir"))

        with open(os.path.join(self.dir1, "subdir", "file1.txt"), "w") as f:
            f.write("content1")
        with open(os.path.join(self.dir2, "subdir", "file2.txt"), "w") as f:
            f.write("content2")

        # Force macOS path by mocking renameat2 as None
        with mock.patch("gcl_sdk.common.utils.renameat2", None):
            utils.swap_dirs(self.dir1, self.dir2)

        # Verify swap occurred including subdirectories
        self.assertTrue(os.path.exists(os.path.join(self.dir1, "subdir", "file2.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dir2, "subdir", "file1.txt")))
