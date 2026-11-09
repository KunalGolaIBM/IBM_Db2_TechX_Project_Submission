import subprocess

def db2(sql):
    cmd = ['docker', 'exec', '-i', 'finsight-db2', 'su', '-', 'db2inst1', '-c', f'db2 connect to FINDB > /dev/null && db2 -x "{sql}"']
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout.strip()

print('--- USERS COLUMNS ---')
print(db2("SELECT colname, typename, length, nulls FROM syscat.columns WHERE tabschema = 'FINSIGHT' AND tabname = 'USERS' ORDER BY colno"))

print('\n--- USER_SESSIONS COLUMNS ---')
print(db2("SELECT colname, typename, length, nulls FROM syscat.columns WHERE tabschema = 'FINSIGHT' AND tabname = 'USER_SESSIONS' ORDER BY colno"))

print('\n--- USER_SESSIONS CONSTRAINTS ---')
print(db2("SELECT constname, type FROM syscat.tabconst WHERE tabschema = 'FINSIGHT' AND tabname = 'USER_SESSIONS'"))

print('\n--- USER_SESSIONS INDEXES ---')
print(db2("SELECT indname, colnames FROM syscat.indexes WHERE tabschema = 'FINSIGHT' AND tabname = 'USER_SESSIONS'"))

print('\n--- ROW COUNTS ---')
print('USERS count:', db2("SELECT count(user_id) FROM FINSIGHT.USERS"))
print('USER_SESSIONS count:', db2("SELECT count(session_token_hash) FROM FINSIGHT.USER_SESSIONS"))
print('TRANSACTIONS count:', db2("SELECT count(transaction_id) FROM FINSIGHT.TRANSACTIONS"))
print('TRANSACTION_EMBEDDINGS count:', db2("SELECT count(transaction_id) FROM FINSIGHT.TRANSACTION_EMBEDDINGS"))
print('LANGCHAIN_DB2_STORE count:', db2("SELECT count(id) FROM FINSIGHT.LANGCHAIN_DB2_STORE"))
print('MIGRATIONS applied:\n', db2("SELECT migration_id FROM FINSIGHT.SCHEMA_MIGRATIONS ORDER BY migration_id"))
