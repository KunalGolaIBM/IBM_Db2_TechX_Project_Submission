from backend.repositories import Repository


class FakeDb:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return []


def test_repository_uses_placeholders():
    db = FakeDb()
    Repository(db).get_learning_history("x' OR 1=1 --", 5)
    assert "x' OR 1=1" not in db.calls[0][0]
    assert db.calls[0][1] == ("x' OR 1=1 --", 5)
