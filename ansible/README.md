# ansible/

Deploy playbooks for VPS. Empty until the deployment epic begins
(post-MVP-foundation).

Patterns to inherit from `vps_management` when this lands:

- `vault.yml.example` template, `vault.yml` gitignored.
- `99-verify.yml` health gate that asserts the container is up and
  healthy after deploy.
- One playbook per layer (bootstrap, app deploy, secrets rotation).

The eventual goal: `ansible-playbook -i inventory deploy.yml` brings up
a fresh VPS and starts the FluentLoop container with secrets loaded
from the vault.
