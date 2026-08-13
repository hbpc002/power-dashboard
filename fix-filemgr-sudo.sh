#!/bin/bash
# One-time privileged setup: lets the 8899 dashboard delete files it doesn't own
# inside /home/hbpc/video_projects_douyin without prompting for a password.
# Run:  sudo bash /home/hbpc/fix-filemgr-sudo.sh
set -e
install -m 440 -o root -g root /tmp/opencode/99-filemgr-sudoers /etc/sudoers.d/99-filemgr
/usr/sbin/visudo -c -f /etc/sudoers.d/99-filemgr
echo "OK — passwordless delete enabled for video_projects_douyin."
echo "Any files created by other users in that tree can now be deleted from the 8899 dashboard."