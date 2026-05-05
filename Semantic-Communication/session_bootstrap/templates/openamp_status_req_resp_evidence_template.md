# OpenAMP STATUS_REQ/RESP Evidence

- generated_at: `{{generated_at}}`
- run_id: `{{run_id}}`
- board: `{{board}}`
- firmware: `{{firmware}}`
- service_name: `{{service_name}}`

## Layer Check

- remoteproc0: {{remoteproc_state}}
- rpmsg channel: {{rpmsg_channel}}
- rpmsg ctrl device: {{rpmsg_ctrl}}
- rpmsg endpoint device: {{rpmsg_dev}}

## Request

- command: `{{command}}`
- job_id: `{{job_id}}`
- seq: `{{seq}}`
- tx_format: `{{tx_format}}`
- tx_artifacts: {{tx_artifacts}}

## Response

- transport_status: `{{transport_status}}`
- protocol_semantics: `{{protocol_semantics}}`
- rx_summary: {{rx_summary}}
- rx_artifacts: {{rx_artifacts}}

## Conclusion

- transport_verified: {{transport_verified}}
- protocol_semantics_verified: {{protocol_semantics_verified}}
- blocker: {{blocker}}

## Evidence Bundle

{{evidence_bundle}}
