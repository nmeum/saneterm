import os

# This code is highly linux-specific and requires proc to be mounted in
# order to retrieve information about the current foreground process.

def __proc_dir(pid):
    return os.path.join("/proc", str(pid))

def cwd(pid):
    cwd = os.path.join(__proc_dir(pid), "cwd")
    dest = os.readlink(cwd)

    return os.path.abspath(dest)

def executable(pid):
    exec = os.path.join(__proc_dir(pid), "exe")
    dest = os.readlink(exec)

    # XXX: Does this work with busybox symlinks i.e. /bin/sh → /bin/busybox?
    return os.path.abspath(dest)
