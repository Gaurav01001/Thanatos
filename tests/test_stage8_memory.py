import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.engine.memory.user_memory import UserMemory
from src.engine.security.validator import SecurityValidator


class TestStage8Memory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_user_memory.db")
        self.memory = UserMemory(db_path=self.db_path)
        self.validator = SecurityValidator()

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # 1. UserMemory SQLite CRUD & Persistence
    # ------------------------------------------------------------------
    def test_profile_facts_crud(self):
        # Create
        self.memory.set_fact("name", "Gaurav")
        self.assertEqual(self.memory.get_fact("name"), "Gaurav")

        # Case normalization check (case-insensitive keys)
        self.assertEqual(self.memory.get_fact("NAME"), "Gaurav")
        self.assertEqual(self.memory.get_fact("Name"), "Gaurav")

        # Update / Overwrite
        self.memory.set_fact("name", "Alex")
        self.assertEqual(self.memory.get_fact("name"), "Alex")

        # Non-existent key
        self.assertIsNone(self.memory.get_fact("occupation"))

        # Delete
        deleted = self.memory.delete_fact("name")
        self.assertTrue(deleted)
        self.assertIsNone(self.memory.get_fact("name"))

        # Delete non-existent
        deleted_again = self.memory.delete_fact("name")
        self.assertFalse(deleted_again)

    def test_episodic_notes_and_deduplication(self):
        self.memory.add_note("Prefers dark mode in IDE")
        self.memory.add_note("Prefers dark mode in IDE")  # Duplicate
        self.memory.add_note("Codes primarily in Python and Rust")

        all_mem = self.memory.get_all_memories()
        notes = all_mem["notes"]
        self.assertEqual(len(notes), 2)
        note_contents = [n["content"] for n in notes]
        self.assertIn("Prefers dark mode in IDE", note_contents)
        self.assertIn("Codes primarily in Python and Rust", note_contents)

    def test_persistence_across_reloads(self):
        # Store facts in first instance
        self.memory.set_fact("role", "Architect")
        self.memory.add_note("Likes mechanical keyboards")

        # Create a second instance connected to the exact same SQLite database
        reloaded_memory = UserMemory(db_path=self.db_path)
        self.assertEqual(reloaded_memory.get_fact("role"), "Architect")

        all_mem = reloaded_memory.get_all_memories()
        self.assertEqual(len(all_mem["notes"]), 1)
        self.assertEqual(all_mem["notes"][0]["content"], "Likes mechanical keyboards")

    def test_clear_all_wipes_everything(self):
        self.memory.set_fact("name", "Gaurav")
        self.memory.add_note("Testing wipe functionality")
        self.memory.clear_all()

        all_mem = self.memory.get_all_memories()
        self.assertEqual(all_mem["profile"], {})
        self.assertEqual(all_mem["notes"], [])
        self.assertIsNone(self.memory.get_fact("name"))

    def test_build_context_prompt(self):
        # Empty memory produces empty context
        self.assertEqual(self.memory.build_context_prompt(), "")

        # Populated memory produces structured markdown prompt block
        self.memory.set_fact("name", "Gaurav")
        self.memory.set_fact("language", "Python")
        self.memory.add_note("Uses Tokyo Night theme")

        prompt = self.memory.build_context_prompt()
        self.assertIn("[Known User Information & Preferences]", prompt)
        self.assertIn("Gaurav", prompt)
        self.assertIn("- Language: Python", prompt)
        self.assertIn("- Uses Tokyo Night theme", prompt)

    # ------------------------------------------------------------------
    # 2. SecurityValidator Gates for Memory
    # ------------------------------------------------------------------
    def test_security_validator_safe_memory_actions(self):
        # save_memory is SAFE
        status, reason = self.validator.validate_intent({
            "action": "save_memory",
            "target": "name: Gaurav",
            "folder": "profile",
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

        # recall_memory is SAFE
        status, reason = self.validator.validate_intent({
            "action": "recall_memory",
            "target": "name",
            "folder": None,
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

        # delete_memory is SAFE
        status, reason = self.validator.validate_intent({
            "action": "delete_memory",
            "target": "name",
            "folder": None,
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

    def test_security_validator_wipe_memory_requires_confirm(self):
        status, reason = self.validator.validate_intent({
            "action": "wipe_memory",
            "target": None,
            "folder": None,
        })
        self.assertEqual(status, "CONFIRM")
        self.assertIn("requires user confirmation", reason)

    # ------------------------------------------------------------------
    # 3. Brain Intent Classification & Fast-Paths
    # ------------------------------------------------------------------
    @patch("src.engine.brain.brain.RAGManager")
    def test_brain_fast_path_intent_classification(self, mock_rag):
        from src.engine.brain.brain import Brain

        brain = Brain()

        # Name saving
        intent = brain.get_intent("my name is Gaurav")
        self.assertEqual(intent["action"], "save_memory")
        self.assertEqual(intent["target"], "name: gaurav")
        self.assertEqual(intent["folder"], "profile")

        # General remember
        intent = brain.get_intent("remember that I like clean code")
        self.assertEqual(intent["action"], "save_memory")
        self.assertEqual(intent["target"], "i like clean code")
        self.assertEqual(intent["folder"], "note")

        # Recall name
        intent = brain.get_intent("what is my name")
        self.assertEqual(intent["action"], "recall_memory")
        self.assertEqual(intent["target"], "name")

        # Recall all memories
        intent = brain.get_intent("what do you remember about me")
        self.assertEqual(intent["action"], "recall_memory")
        self.assertIsNone(intent["target"])

        # Delete memory
        intent = brain.get_intent("forget my name")
        self.assertEqual(intent["action"], "delete_memory")
        self.assertEqual(intent["target"], "name")

        # Wipe memory
        intent = brain.get_intent("clear all memories")
        self.assertEqual(intent["action"], "wipe_memory")

    # ------------------------------------------------------------------
    # 4. Brain Memory Helpers
    # ------------------------------------------------------------------
    @patch("src.engine.brain.brain.RAGManager")
    def test_brain_memory_helper_methods(self, mock_rag):
        from src.engine.brain.brain import Brain

        brain = Brain()
        # Point brain's memory to our isolated test db
        brain._user_memory = self.memory

        # Save profile fact
        res = brain.save_user_memory("name: Gaurav", folder="profile")
        self.assertIn("Gaurav", res)

        # Recall specific fact
        recall_res = brain.recall_user_memory("name")
        self.assertEqual(recall_res, "Your name is Gaurav.")

        # Save note
        res = brain.save_user_memory("likes async programming", folder="note")
        self.assertIn("committed that to memory", res)

        # Recall all
        all_res = brain.recall_user_memory("all")
        self.assertIn("Gaurav", all_res)
        self.assertIn("likes async programming", all_res)

        # Delete fact
        del_res = brain.delete_user_memory("name")
        self.assertIn("forgotten your name", del_res)

        # Wipe
        wipe_res = brain.wipe_user_memory()
        self.assertIn("completely erased", wipe_res)
        self.assertIn("empty", brain.recall_user_memory())


if __name__ == "__main__":
    unittest.main()
