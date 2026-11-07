title: How to collect useful Db2 Developer Extension logs for an issue
category: EXTENSION
url: https://ibm.github.io/db2developerextension-about/docs/troubleshooting/opening-an-issue-and-providinglogs.html

In VS Code open View, Output and select the "Db2 Extension" channel. For completion problems the troubleshooting guide may ask you to enable the setting vscodedb2.toggleCompletionDebugLogging. Run "Developer: Open Extension Logs Folder" from the Command Palette and look for the IBM Db2 folders (including IBM.db2-for-luw when present). Attach only logs relevant to the problem after removing passwords, tokens, connection strings and hostnames, and note the approximate time of failure.
Good issues: search existing issues first, one problem per issue, numbered reproduction steps, separate actual and expected behaviour, and say whether it happens every time.
