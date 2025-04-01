sshpass -f .ssh-pw ssh -o StrictHostKeychecking=no  -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password -o PubkeyAuthentication=no root@10.100.50.1 "kill 1"
