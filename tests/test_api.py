import os
import unittest
import tempfile

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.api.api import app
from io import BytesIO
from utils.auth import verify_token


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        self.mock_user = MagicMock()
        self.mock_user.username = "testuser"
        self.mock_user.password = "secure_password"

        self.auth_patcher = patch('utils.auth.verify_token')
        self.mock_verify_token = self.auth_patcher.start()
        self.mock_verify_token.return_value = self.mock_user

        # Override the verify_token dependency in the FastAPI app
        # Ignor the type error here, as this is a workaround for the test environment
        app.dependency_overrides[verify_token] = lambda: self.mock_user

    def tearDown(self):
        self.auth_patcher.stop()
        # Ignor the type error here, as this is a workaround for the test environment
        app.dependency_overrides.clear()

    def test_login_success(self):
        with patch('src.api.api.authenticate') as mock_authenticate:
            mock_authenticate.return_value = True
            with patch('src.api.api.create_token') as mock_create_token:
                mock_create_token.return_value = "test_token"
                response = self.client.post(
                    "/api/login",
                    data={"username": self.mock_user.username, "password": self.mock_user.password}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"access_token": "test_token", "token_type": "bearer"})

    def test_login_failure(self):
        with patch('src.api.api.authenticate') as mock_authenticate:
            mock_authenticate.return_value = None
            response = self.client.post(
                "/api/login",
                data={"username": self.mock_user.username, "password": "wrong_password"}
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Invalid credentials"})

    def test_get_call_history(self):
        # Fix the mock data structure to match CallHistoryLite model
        dummy_history = [{"call_id": "123abc", "caller": "User 1", "start_time": "2025-07-21T10:00:00"}]
        with patch("src.api.api.get_call_history_lite", return_value=dummy_history) as mock_hist:
            resp = self.client.get("/api/history")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), dummy_history)
            mock_hist.assert_called_once()

    def test_get_call_details(self):
        dummy_call_detail = {
            "call_id": "123abc",
            "caller": "User 1",
            "start_time": "2025-07-21T10:00:00",
            "end_time": "2025-07-21T10:15:00",
            "participants": [
                {
                    "type": "API",
                    "call_id": "123abc",
                    "user": "User 1",
                    "ssrc": "123456",
                    "ip_address": "192.168.1.1",
                    "media_port": 5000,
                    "mime_type": "opus",
                    "server_ip": "10.0.0.1",
                    "server_port": 5060
                }
            ],
            "talking_interval": [
                {
                    "type": "speech",
                    "call_id": "123abc",
                    "ssrc": "123456",
                    "start": 0,
                    "end": 10
                }
            ]
        }

        with patch("src.api.api.get_call_for_api", return_value=dummy_call_detail) as mock_details:
            resp = self.client.get(
                "/api/call-details",
                params= {"call_id": "123abc"}
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), dummy_call_detail)
            mock_details.assert_called_once_with("123abc")

        with patch("src.api.api.get_call_for_api", return_value=None) as mock_details:
            resp = self.client.get(
                "/api/call-details",
                params= {"call_id": "not_exist"}
            )
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.json(), {"detail": "Call not found"})
            mock_details.assert_called_once_with("not_exist")

    def test_change_mode_file_to_live(self):
        with patch("src.api.api.ProgramStateManager") as mock_psm_cls:
            with patch("src.api.api.interface", "eth0"):
                mock_psm = mock_psm_cls.return_value
                mock_psm.get_mode.return_value = "file"

                response = self.client.post(
                    "/api/mode",
                    data={"mode": "live"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"mode": "live", "using": "eth0"})
                mock_psm_cls.assert_called_once()
                mock_psm.get_mode.assert_called_once()
                mock_psm.switch_mode.assert_called_once_with("live", "eth0")

    def test_change_mode_live_to_live(self):
        with patch("src.api.api.ProgramStateManager") as mock_psm_cls:
            with patch("src.api.api.interface", "eth0"):
                mock_psm = mock_psm_cls.return_value
                mock_psm.get_mode.return_value = "live"

                response = self.client.post(
                    "/api/mode",
                    data={"mode": "live"}
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), None)
                mock_psm_cls.assert_called_once()
                mock_psm.get_mode.assert_called_once()
                mock_psm.switch_mode.assert_not_called()

    def test_change_mode_live_to_file_with_file(self):
        temp_file_content = b"dummy pcap data"
        temp_file_path = "test.pcap"

        with patch("src.api.api.ProgramStateManager") as mock_psm_cls:
            with patch("src.api.api.switch_mode") as mock_switch_mode:
                mock_psm = mock_psm_cls.return_value
                mock_psm.get_mode.return_value = "live"

                response = self.client.post(
                    "/api/mode",
                    data={"mode": "file"},
                    files={"file": (temp_file_path, BytesIO(temp_file_content))}
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["mode"], "file")
                mock_psm_cls.assert_called_once()
                mock_psm.get_mode.assert_not_called()

                mode_arg, full_path = mock_switch_mode.call_args[0]

                self.assertEqual(mode_arg, "file")
                self.assertTrue(os.path.basename(full_path), temp_file_path)

    def test_change_mode_live_to_file_without_file(self):
        with patch("src.api.api.ProgramStateManager") as mock_psm_cls:
            mock_psm = mock_psm_cls.return_value

            response = self.client.post(
                "/api/mode",
                data={"mode": "file"}
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"detail": "File is required for file mode"})
            mock_psm.assert_not_called()

    def test_program_mode_endpoint(self):
        with patch("src.api.api.ProgramStateManager") as mock_psm_cls:
            mock_psm = mock_psm_cls.return_value
            mock_psm.get_mode.return_value = "live"
            response = self.client.get("/api/server-mode")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"mode": "live"})
            self.assertEqual(mock_psm.get_mode.call_count, 2)

        with patch("src.api.api.ProgramStateManager") as mock_psm_cls:
            mock_psm = mock_psm_cls.return_value
            mock_psm.get_mode.return_value = None
            response = self.client.get("/api/server-mode")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Program mode not set"})
            mock_psm.get_mode.assert_called_once()

    def test_set_new_password(self):
        new_password = "new_secure_password"
        with patch("src.api.api.verify_password", return_value=True) as mock_get_mode:
            with patch("src.api.api.hash_password", return_value=new_password) as mock_hash_password:
                with patch("src.api.api.change_password") as mock_change_password:
                    response = self.client.post(
                        "/api/change-password",
                        data={
                            "old_password": self.mock_user.password,
                            "new_password": new_password,
                        }
                    )
                    self.assertEqual(response.status_code, 200)
                    mock_change_password.assert_called_once_with(self.mock_user.username, new_password)
                    self.assertEqual(response.json(), {"success": True, "message": "Password changed successfully"})

    def test_set_new_password_incorrect_old(self):
        with patch("src.api.api.verify_password", return_value=False) as mock_get_mode:
            response = self.client.post(
                "/api/change-password",
                data={
                    "old_password": "wrong_password",
                    "new_password": "new_secure_password",
                }
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Old password is incorrect"})
            mock_get_mode.assert_called_once_with("wrong_password", self.mock_user.password)

    def test_set_new_user(self):
        new_username = "newuser"
        new_password = "secure_password"
        with patch("src.api.api.hash_password", return_value=new_password) as mock_hash_password:
            with patch("src.api.api.set_user", return_value= True) as mock_set_user:
                response = self.client.post(
                    "/api/create-user",
                    data={
                        "username": new_username,
                        "password": new_password,
                    }
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"success": True, "message": "User created successfully"})
                mock_set_user.assert_called_once_with(new_username, new_password)

    def test_set_new_user_already_exists(self):
        new_username = "newuser"
        new_password = "secure_password"
        with patch("src.api.api.hash_password", return_value=new_password) as mock_hash_password:
            with patch("src.api.api.set_user", return_value=None) as mock_set_user:
                response = self.client.post(
                    "/api/create-user",
                    data={
                        "username": new_username,
                        "password": new_password,
                    }
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"detail": "User already exists"})
                mock_set_user.assert_called_once_with(new_username, new_password)

    def test_set_new_user_not_work(self):
        new_username = "newuser"
        new_password = "secure_password"
        with patch("src.api.api.hash_password", return_value=new_password) as mock_hash_password:
            with patch("src.api.api.set_user", return_value =False) as mock_set_user:
                response = self.client.post(
                    "/api/create-user",
                    data={
                        "username": new_username,
                        "password": new_password,
                    }
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"success": False, "message": "Failed to create user"})
                mock_set_user.assert_called_once_with(new_username, new_password)

    def test_delete_user_not_exists(self):
        username = "testuser"
        password = "secure_password"
        with patch("src.api.api.get_user", return_value=None) as mock_get_user:
            response = self.client.post(
                "/api/delete-user",
                data={
                    "username": username,
                    "password": password,
                }
            )
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail" :"User not found"})
            mock_get_user.assert_called_once_with(username)

    def test_delete_user_incorrect_password(self):
        username = "testuser"
        password = "secure_password"

        mock_existing_user = MagicMock()
        mock_existing_user.username = username
        mock_existing_user.password = password

        with patch("src.api.api.get_user", return_value=mock_existing_user) as mock_get_user:
            with patch("src.api.api.verify_password", return_value=False) as mock_verify_password:
                response = self.client.post(
                    "/api/delete-user",
                    data={
                        "username": username,
                        "password": password,
                    }
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"detail": "Incorrect password"})
                mock_get_user.assert_called_once_with(username)
                mock_verify_password.assert_called_once_with(password, mock_existing_user.password)

    def test_delete_user(self):
        username = "testuser"
        password = "secure_password"

        mock_existing_user = MagicMock()
        mock_existing_user.username = username
        mock_existing_user.password = password

        with patch("src.api.api.get_user", return_value=mock_existing_user) as mock_get_user:
            with patch("src.api.api.verify_password", return_value=True) as mock_verify_password:
                with patch("src.api.api.remove_user", return_value=True) as mock_remove_user:
                    response = self.client.post(
                        "/api/delete-user",
                        data={
                            "username": username,
                            "password": password,
                        }
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {"success": True, "message": "User deleted successfully"})
                    mock_get_user.assert_called_once_with(username)
                    mock_verify_password.assert_called_once_with(password, mock_existing_user.password)
                    mock_remove_user.assert_called_once_with(username)

    def test_delete_user_not_removed(self):
        username = "testuser"
        password = "secure_password"

        mock_existing_user = MagicMock()
        mock_existing_user.username = username
        mock_existing_user.password = password

        with patch("src.api.api.get_user", return_value=mock_existing_user) as mock_get_user:
            with patch("src.api.api.verify_password", return_value=True) as mock_verify_password:
                with patch("src.api.api.remove_user", return_value=False) as mock_remove_user:
                    response = self.client.post(
                        "/api/delete-user",
                        data={
                            "username": username,
                            "password": password,
                        }
                    )
                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(response.json(), {"detail": "Failed to delete user"})
                    mock_get_user.assert_called_once_with(username)
                    mock_verify_password.assert_called_once_with(password, mock_existing_user.password)
                    mock_remove_user.assert_called_once_with(username)

    def test_log_stream(self):
        with patch("src.api.api.app_logger.info") as mock_logger:
            with patch("src.api.api.EventSourceResponse") as mock_sse:
                mock_sse.return_value = MagicMock()

                response = self.client.get(
                    "/api/logs/stream"
                )

                self.assertEqual(response.status_code, 200)

                mock_logger.assert_called_once_with("New sse-client connected")

                mock_sse.assert_called_once()
