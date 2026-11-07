title: SQL30082N / SQL1639N authentication failures
category: AUTHENTICATION

SQL30082N reason code 24 means the user ID or password is wrong; reason 1 means the password expired. In the Community Edition container, the instance user is db2inst1 and its password is the DB2INST1_PASSWORD value given at container creation. Changing the environment variable later does not change the existing user's password.
Never paste the password into an issue; say only which reason code appears.
