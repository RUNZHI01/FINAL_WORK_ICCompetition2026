# run_id=resource_profile_smoke_20260312_001
# command_mode=remote_command
# trusted_variant=current
# target_description=remote:bash -lc 'echo smoke-host=$(hostname); echo started=$(date -Iseconds); sleep 3; echo done=$(date -Iseconds)'
bash '/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/ssh_with_password.sh' --host '100.121.87.73' --user 'user' --pass 'user' --port '22' -- bash -lc 'echo smoke-host=$(hostname); echo started=$(date -Iseconds); sleep 3; echo done=$(date -Iseconds)'
