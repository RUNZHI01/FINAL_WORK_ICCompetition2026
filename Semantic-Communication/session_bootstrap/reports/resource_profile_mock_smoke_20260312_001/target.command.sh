# run_id=resource_profile_mock_smoke_20260312_001
# command_mode=smoke
# trusted_variant=current
# target_description=remote:bash -lc 'echo resource-profile-smoke host=$(hostname); echo started=$(date -Iseconds); sleep 3; echo finished=$(date -Iseconds)'
bash '/tmp/mock_ssh_with_password.sh' --host '100.121.87.73' --user 'user' --pass '<REDACTED>' --port '22' -- bash -lc 'echo resource-profile-smoke host=$(hostname); echo started=$(date -Iseconds); sleep 3; echo finished=$(date -Iseconds)'
