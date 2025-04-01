sshpass -f .ssh-pw ssh -N -o StrictHostKeychecking=no  -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password -o PubkeyAuthentication=no -L 8080:localhost:8080 root@10.100.50.1
