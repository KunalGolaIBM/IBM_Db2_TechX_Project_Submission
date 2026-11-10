from api.app.db import connection_error_message


def test_db_connection_error_message_keeps_diagnostics_without_dsn_credentials():
    message = connection_error_message(Exception(
        "[IBM] DATABASE=ANNASETU;HOSTNAME=127.0.0.1;UID=db2inst1;PWD=synthetic-secret; "
        "SQLSTATE=08001 SQLCODE=-30081"
    ))
    assert "SQLSTATE 08001" in message
    assert "SQLCODE -30081" in message
    assert "synthetic-secret" not in message
    assert "PWD" not in message
