Here is a list of steps that need to be manually taken after running this Ansible playbook.


# tailscale

- Run `sudo tailscale up`
- Use the link to add the machine to your tailnet
- Change the IPv4 machine to `100.100.50.50`
- Disable key expiry for this machine
- Edit route settings for this machine and enable subnets and exit node


# thinkpad-backup

- Set up the systemd service in the thinkpad to automatically back up to my server


# grafana

- Import the dashboards in `docs/grafana/dashboards`
- Import the alert rules in `docs/grafana/alert-rules`


# papra

- Create user
- Upload documents


# jellyfin

- Create user
- Add media


# immich

- Create user
- Add assets


# synapse

- User `marc` has been created by ansible


# bot-expenses

- Create room for the bot to send the summary of the expenses
- Get the room ID
- Update the `SUMMARY_ROOM_ID` in `/opt/bot-expenses/bot-expenses.env`

