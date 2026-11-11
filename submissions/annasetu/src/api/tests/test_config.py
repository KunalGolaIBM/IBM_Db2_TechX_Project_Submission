from api.app.config import Settings


def test_test_server_can_allow_5174_without_changing_production_defaults():
    qa = Settings(cors_origins="http://127.0.0.1:5174")
    production_example = Settings(cors_origins="http://localhost:5173,http://127.0.0.1:5173")

    assert qa.allowed_origins == ["http://127.0.0.1:5174"]
    assert production_example.allowed_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
