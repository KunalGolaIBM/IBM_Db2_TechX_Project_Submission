import subprocess


def deploy(cmd):
    return subprocess.run(cmd, shell=True)
