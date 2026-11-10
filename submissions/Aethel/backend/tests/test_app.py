import asyncio
import os
import unittest
from contextlib import asynccontextmanager
from unittest.mock import PropertyMock, patch

from fastapi.testclient import TestClient

from backend import app as app_module
from backend.companion.agent import AgentConfigurationError, reply_to
from backend.companion.db import Db2UnavailableError, LocalMemoryStore


class AethelApiTests(unittest.TestCase):
    def setUp(self):
        @asynccontextmanager
        async def test_lifespan(application):
            application.state.db2_ready = True
            application.state.local_mode = False
            application.state.db2_required = False
            application.state.storage = app_module.store
            yield

        self.lifespan_patch = patch.object(
            app_module.app.router, "lifespan_context", test_lifespan
        )
        self.lifespan_patch.start()
        self.client_context = TestClient(app_module.app, base_url="http://localhost")
        self.client = self.client_context.__enter__()
        self.profile = {
            "name": "Sam",
            "time_zone": "Asia/Kolkata",
            "check_ins_enabled": True,
        }

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.lifespan_patch.stop()

    def test_onboarding_validates_and_persists_profile(self):
        with patch.object(app_module.store, "save_profile") as save_profile:
            response = self.client.put(
                "/api/profile",
                json={
                    "name": "  Sam  ",
                    "time_zone": "Not/AZone",
                    "check_ins_enabled": True,
                },
            )
            self.assertEqual(response.status_code, 422)
            save_profile.assert_not_called()

            response = self.client.put(
                "/api/profile",
                json={
                    "name": "  Sam  ",
                    "time_zone": "Asia/Kolkata",
                    "check_ins_enabled": True,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), self.profile)
            save_profile.assert_called_once()

    def test_blank_profile_and_extra_fields_are_rejected(self):
        response = self.client.put(
            "/api/profile",
            json={"name": "   ", "time_zone": "UTC", "check_ins_enabled": True},
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.put(
            "/api/profile",
            json={**self.profile, "unknown": "not accepted"},
        )
        self.assertEqual(response.status_code, 422)

    def test_task_uses_profile_zone_and_rejects_nonexistent_local_time(self):
        with patch.object(app_module.store, "get_profile", return_value=self.profile):
            with patch.object(app_module.store, "create_task") as create_task:
                response = self.client.post(
                    "/api/tasks",
                    json={
                        "task_type": "pill",
                        "description": " Usual evening reminder ",
                        "due_at": "2026-11-10T18:00",
                    },
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["description"], "Usual evening reminder")
                self.assertEqual(response.json()["due_at"], "2026-11-10T12:30:00+00:00")
                create_task.assert_called_once()

        chicago = {**self.profile, "time_zone": "America/Chicago"}
        with (
            patch.object(app_module.store, "get_profile", return_value=chicago),
            patch.object(app_module.store, "create_task") as create_task,
        ):
            response = self.client.post(
                "/api/tasks",
                json={
                    "task_type": "health_check",
                    "description": "DST gap",
                    "due_at": "2026-03-08T02:30",
                },
            )
            self.assertEqual(response.status_code, 422)
            create_task.assert_not_called()

    def test_task_requires_profile_and_known_type(self):
        with patch.object(app_module.store, "get_profile", return_value=None):
            response = self.client.post(
                "/api/tasks",
                json={
                    "task_type": "pill",
                    "description": "Evening reminder",
                    "due_at": "2026-11-10T18:00",
                },
            )
        self.assertEqual(response.status_code, 409)

        response = self.client.post(
            "/api/tasks",
            json={
                "task_type": "diagnosis",
                "description": "Do something",
                "due_at": "2026-11-10T18:00",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_chat_persists_turn_and_requires_profile(self):
        with patch.object(app_module.store, "get_profile", return_value=None):
            response = self.client.post("/api/chat", json={"message": "Hello"})
        self.assertEqual(response.status_code, 409)

        with (
            patch.object(app_module.store, "get_profile", return_value=self.profile),
            patch.object(app_module.store, "get_history", return_value=[]),
            patch.object(app_module.store, "add_turn") as add_turn,
            patch.object(app_module, "reply_to", return_value="I’m listening.") as agent,
        ):
            response = self.client.post("/api/chat", json={"message": "I had a hard day."})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reply": "I’m listening."})
        add_turn.assert_called_once()
        agent.assert_called_once_with("I had a hard day.", self.profile, [])

    def test_due_reminders_and_review_board(self):
        with (
            patch.object(app_module.store, "claim_due_tasks", return_value=[]) as claim,
            patch.object(app_module.store, "list_reviews", return_value=[]) as list_reviews,
        ):
            due = self.client.get("/api/reminders/due")
            reviews = self.client.get("/api/reviews")
        self.assertEqual(due.status_code, 200)
        self.assertEqual(reviews.status_code, 200)
        claim.assert_called_once()
        list_reviews.assert_called_once()

        with patch.object(app_module.store, "create_review") as create_review:
            response = self.client.post(
                "/api/reviews",
                json={"name": "Neighbor", "message": "Care begins with listening."},
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Neighbor")
        self.assertIn("created_at", response.json())
        create_review.assert_called_once()

    def test_status_establishes_a_session_before_parallel_private_requests(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("aethel_session=", response.headers["set-cookie"])

    def test_db2_not_ready_is_reported_as_service_unavailable(self):
        app_module.app.state.db2_ready = False
        response = self.client.get("/api/profile")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Db2 is not ready. Configure the local TESTDB connection and initialize its tables.")

    def test_local_fallback_uses_memory_and_reports_storage_mode(self):
        app_module.app.state.storage = LocalMemoryStore()
        app_module.app.state.db2_ready = False
        app_module.app.state.local_mode = True

        status_response = self.client.get("/api/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertFalse(status_response.json()["db2_ready"])
        self.assertTrue(status_response.json()["local_mode"])
        self.assertEqual(status_response.json()["storage_mode"], "local")
        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["storage_mode"], "local")

        saved = self.client.put("/api/profile", json=self.profile)
        self.assertEqual(saved.status_code, 200)
        loaded = self.client.get("/api/profile")
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json(), self.profile)

        task = self.client.post(
            "/api/tasks",
            json={
                "task_type": "pill",
                "description": "Evening reminder",
                "due_at": "2020-01-01T18:00:00+00:00",
            },
        )
        self.assertEqual(task.status_code, 201)
        self.assertEqual(len(self.client.get("/api/tasks").json()), 1)
        due = self.client.get("/api/reminders/due")
        self.assertEqual(len(due.json()), 1)
        self.assertEqual(self.client.get("/api/reminders/due").json(), [])
        self.assertEqual(
            self.client.post(f"/api/tasks/{task.json()['id']}/complete").status_code,
            200,
        )

        review = self.client.post(
            "/api/reviews",
            json={"name": "Neighbor", "message": "A thoughtful prototype."},
        )
        self.assertEqual(review.status_code, 201)
        self.assertEqual(self.client.get("/api/reviews").json()[0]["id"], review.json()["id"])

    def test_lifespan_falls_back_when_db2_initialization_fails(self):
        async def run_lifespan():
            async with app_module.lifespan(app_module.app):
                self.assertFalse(app_module.app.state.db2_ready)
                self.assertTrue(app_module.app.state.local_mode)
                self.assertIs(app_module.app.state.storage, app_module.local_store)

        with (
            patch.dict(os.environ, {"REQUIRE_DB2": "false"}),
            patch.object(app_module, "production", False),
            patch.object(
                type(app_module.db2_store),
                "is_configured",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(
                app_module.db2_store,
                "initialize",
                side_effect=Db2UnavailableError("driver binary compatibility failure"),
            ),
            patch.object(app_module.logger, "exception"),
        ):
            asyncio.run(run_lifespan())

    def test_home_assets_and_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Aethel", response.content)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertIn(b"24/7", response.content)
        self.assertIn(b"AGENTIC", response.content)
        self.assertIn(b'aria-label="Site navigation"', response.content)
        self.assertNotIn(b'site-header', response.content)
        self.assertNotIn("AETHEL · ALWAYS HERE".encode(), response.content)
        self.assertIn(b'/assets/Purple%20robot.jpg', response.content)
        self.assertIn(b'class="hero-background"', response.content)
        self.assertIn(b'EMPATHETIC AI COMPANION ACTING', response.content)
        self.assertIn(b'POWERED BY IBM DB2 &amp; AGENTIC AI', response.content)

        image = self.client.get("/assets/Purple%20robot.jpg")
        self.assertEqual(image.status_code, 200)
        self.assertTrue(image.headers["content-type"].startswith("image/jpeg"))

    def test_separate_pages_and_prototype_assets(self):
        pages = {
            "/prototype": (b"profile-form", b"task-form"),
            "/architecture": (b"architecture.png", b"LangGraph"),
            "/community": (b"review-form", b"review-board"),
        }
        for path, markers in pages.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                for marker in markers:
                    self.assertIn(marker, response.content)

        assets = (
            "Purple%20robot.jpg",
            "Dark%20waves%20wallpaper.jpg",
            "asthetic%20wallpaper%204k%20black%20shade.jpg",
            "architecture.png",
        )
        for asset in assets:
            with self.subTest(asset=asset):
                self.assertEqual(self.client.get(f"/assets/{asset}").status_code, 200)

    def test_langgraph_agent_uses_safety_context_and_recent_history(self):
        try:
            from langchain_core.messages import AIMessage, HumanMessage
            from langchain_core.runnables import RunnableLambda
        except ImportError:
            self.skipTest("Install requirements.txt to run the LangGraph integration test.")

        captured = {}

        def fake_model(prompt):
            captured["messages"] = prompt.to_messages()
            return "I’m here with you."

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            patch(
                "langchain_openai.ChatOpenAI",
                return_value=RunnableLambda(fake_model),
            ),
        ):
            response = reply_to(
                "Could you remind me about my pill?",
                {"name": "Sam", "time_zone": "UTC", "check_ins_enabled": True},
                [
                    {"role": "user", "content": "I like a gentle tone."},
                    {"role": "assistant", "content": "Of course."},
                ],
            )

        self.assertEqual(response, "I’m here with you.")
        prompt_messages = captured["messages"]
        self.assertIn("Do not diagnose", prompt_messages[0].content)
        self.assertIn("reminder", prompt_messages[0].content.lower())
        self.assertIn("Friendly check-ins are enabled", prompt_messages[0].content)
        self.assertIsInstance(prompt_messages[1], HumanMessage)
        self.assertIsInstance(prompt_messages[2], AIMessage)

    def test_care_context_classifier_sets_bounded_context(self):
        from backend.companion.agent import _care_context

        medical = _care_context({"message": "Can you recommend a dose?"})
        reminder = _care_context({"message": "Please help with my reminder"})
        general = _care_context({"message": "I feel lonely today"})
        self.assertIn("medical decision", medical["care_context"])
        self.assertIn("user-entered details", reminder["care_context"])
        self.assertIn("user-led next step", general["care_context"])

    def test_agent_requires_provider_credentials(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(AgentConfigurationError):
                reply_to("Hello", self.profile, [])


if __name__ == "__main__":
    unittest.main()
