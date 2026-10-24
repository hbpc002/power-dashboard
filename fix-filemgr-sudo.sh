#!/bin/bash
# One-time privileged setup: lets the 8899 dashboard delete files it doesn't own
# anywhere under /home/hbpc without prompting for a password.
# Run:  sudo bash ~/projects/power-dashboard/fix-filemgr-sudo.sh
set -e
SRC="$(dirname "$(readlink -f "$0")")/sudoers.filemgr"
install -m 440 -o root -g root "$SRC" /etc/sudoers.d/99-filemgr
/usr/sbin/visudo -c -f /etc/sudoers.d/99-filemgr
echo "OK — passwordless delete enabled for everything under /home/hbpc."
echo "The home root itself is excluded. Files owned by other users can now be deleted from the 8899 dashboard."